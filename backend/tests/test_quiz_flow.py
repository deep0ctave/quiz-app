import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import (
    main,
    models,  # noqa: F401
)
from app.database import Base, get_db
from app.models import User


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    test_sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    active_sessions = []

    def override_db():
        session = test_sessions()
        active_sessions.append(session)
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(main, "SessionLocal", test_sessions)
    main.app.dependency_overrides[get_db] = override_db
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()
    for session in active_sessions:
        session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_teacher_can_assign_quiz_for_student_to_take_and_review(client: TestClient) -> None:
    teacher_session = client.post("/auth/login", json={"mobile": "9999999999", "pin": "123456"}).json()
    teacher = {"Authorization": f"Bearer {teacher_session['accessToken']}"}
    question = client.post("/admin/questions", headers=teacher, json={
        "text": "What is 2 + 2?", "options": ["3", "4", "5", "6"],
        "correctOption": 1, "timeLimitSeconds": 30,
    }).json()
    quiz = client.post("/admin/quizzes", headers=teacher, json={
        "title": "Arithmetic", "questionIds": [question["id"]], "showAnswers": True,
    }).json()
    assigned = client.post(f"/admin/quizzes/{quiz['id']}/assignments", headers=teacher,
                           json={"targetType": "ALL"})
    assert assigned.status_code == 201

    student_session = client.post("/auth/register", json={
        "name": "Test Student", "mobile": "9123456781", "pin": "2468",
    }).json()
    student = {"Authorization": f"Bearer {student_session['accessToken']}"}
    listed = client.get("/me/quizzes", headers=student).json()
    assert listed[0]["status"] == "NEW"

    state = client.post(f"/me/quizzes/{quiz['id']}/attempt", headers=student).json()
    assert state["question"]["text"] == "What is 2 + 2?"
    result = client.post(f"/me/attempts/{state['attemptId']}/answers", headers=student,
                         json={"position": 1, "selectedOption": 1}).json()
    assert result["status"] == "COMPLETED"
    assert result["result"]["score"] == 1

    review = client.get(f"/me/results/{state['attemptId']}", headers=student).json()
    assert review["questions"][0]["outcome"] == "CORRECT"
    admin_results = client.get("/admin/attempts", headers=teacher).json()
    assert admin_results["content"][0]["studentName"] == "Test Student"


def test_websocket_room_delivers_questions_checks_answers_and_finishes(client: TestClient) -> None:
    teacher_session = client.post("/auth/login", json={"mobile": "9999999999", "pin": "123456"}).json()
    teacher = {"Authorization": f"Bearer {teacher_session['accessToken']}"}
    question = client.post("/admin/questions", headers=teacher, json={
        "text": "Pick B", "options": ["A", "B", "C", "D"],
        "correctOption": 1, "timeLimitSeconds": 30,
    }).json()
    quiz = client.post("/admin/quizzes", headers=teacher, json={
        "title": "Live quiz", "questionIds": [question["id"]], "showAnswers": True,
    }).json()
    room = client.post("/admin/rooms", headers=teacher, json={"quizId": quiz["id"]}).json()
    student_session = client.post("/auth/register", json={
        "name": "Room Student", "mobile": "9123456782", "pin": "2468",
    }).json()
    client.post(f"/me/rooms/{room['code']}/join",
                headers={"Authorization": f"Bearer {student_session['accessToken']}"})

    with client.websocket_connect(f"/ws/rooms/{room['code']}",
                                  subprotocols=["bearer", teacher_session["accessToken"]]) as host:
        host.receive_json()
        with client.websocket_connect(
            f"/ws/rooms/{room['code']}",
            subprotocols=["bearer", student_session["accessToken"]]
        ) as student:
            host.receive_json()
            student.receive_json()
            host.send_json({"type": "start"})
            assert host.receive_json()["type"] == "started"
            assert host.receive_json()["text"] == "Pick B"
            assert student.receive_json()["type"] == "started"
            assert student.receive_json()["type"] == "question"
            student.send_json({"type": "answer", "option": 1})
            assert student.receive_json() == {"type": "answer_result", "correct": True}
            assert student.receive_json()["type"] == "answer_count"
            assert host.receive_json()["type"] == "answer_count"
            assert student.receive_json()["type"] == "finished"
            assert host.receive_json()["type"] == "finished"


def test_legacy_bcrypt_account_migrates_to_argon2_after_login(client: TestClient) -> None:
    legacy_hash = bcrypt.hashpw(b"2468", bcrypt.gensalt()).decode()
    with main.SessionLocal() as db:
        db.add(User(name="Legacy Student", mobile="9123456783", pin_hash=legacy_hash, role="STUDENT"))
        db.commit()

    response = client.post("/auth/login", json={"mobile": "9123456783", "pin": "2468"})

    assert response.status_code == 200
    with main.SessionLocal() as db:
        upgraded = db.scalar(select(User).where(User.mobile == "9123456783"))
        assert upgraded.pin_hash.startswith("$argon2")


def test_five_wrong_pins_lock_the_account_for_fifteen_minutes(client: TestClient) -> None:
    client.post("/auth/register", json={"name": "Locked Student", "mobile": "9123456784", "pin": "2468"})

    for _ in range(5):
        response = client.post("/auth/login", json={"mobile": "9123456784", "pin": "0000"})
        assert response.status_code == 401

    locked = client.post("/auth/login", json={"mobile": "9123456784", "pin": "2468"})
    assert locked.status_code == 429