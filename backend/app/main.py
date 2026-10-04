import asyncio
import csv
import io
import json
import math
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from fastapi import Depends, FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.models import (
    Assignment,
    Attempt,
    AttemptQuestion,
    Question,
    Quiz,
    QuizQuestion,
    QuizRoom,
    QuizRoomMember,
    RefreshToken,
    StudentGroup,
    User,
    group_members,
)
from app.security import (
    DUMMY_PIN_HASH,
    decode_access_token,
    hash_pin,
    hash_token,
    issue_access_token,
    new_refresh_token,
    verify_pin,
)


def bootstrap_admin() -> None:
    with SessionLocal() as db:
        if not db.scalar(select(User).where(User.mobile == settings.bootstrap_admin_mobile)):
            db.add(User(name=settings.bootstrap_admin_name, mobile=settings.bootstrap_admin_mobile,
                        pin_hash=hash_pin(settings.bootstrap_admin_pin), role="ADMIN"))
            db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    bootstrap_admin()
    yield


app = FastAPI(title="Schoolmela Quiz API", version="0.1.0", lifespan=lifespan,
              docs_url="/swagger-ui.html" if settings.swagger_enabled else None,
              openapi_url="/v3/api-docs" if settings.swagger_enabled else None,
              redoc_url=None)
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")


def camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part.title() for part in tail)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=camel, populate_by_name=True)


class Credentials(ApiModel):
    mobile: str = Field(pattern=r"^\d{10}$")
    pin: str = Field(pattern=r"^\d{4,6}$")


class RegisterRequest(Credentials):
    name: str = Field(min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=254)
    school: str | None = Field(default=None, max_length=150)


class RefreshRequest(ApiModel):
    refresh_token: str


class RoomRequest(ApiModel):
    quiz_id: int


class QuestionRequest(ApiModel):
    text: str = Field(min_length=1, max_length=500)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_option: int = Field(ge=0, le=3)
    time_limit_seconds: int = Field(ge=30, le=120)


class QuizRequest(ApiModel):
    title: str = Field(min_length=1, max_length=150)
    total_time_limit_seconds: int | None = Field(default=None, gt=0)
    show_answers: bool = True
    question_ids: list[int] = Field(min_length=1)


class GroupRequest(ApiModel):
    name: str = Field(min_length=1, max_length=100)


class GroupMembersRequest(ApiModel):
    student_ids: list[int] = Field(min_length=1)


class UserActiveRequest(ApiModel):
    active: bool


class ResetPinRequest(ApiModel):
    pin: str = Field(pattern=r"^\d{4,6}$")


class CreateAdminRequest(Credentials):
    name: str = Field(min_length=1, max_length=100)


class AssignmentRequest(ApiModel):
    target_type: Literal["STUDENT", "GROUP", "ALL"]
    student_id: int | None = None
    group_id: int | None = None
    due_at: datetime | None = None


class AnswerRequest(ApiModel):
    position: int = Field(ge=1)
    selected_option: int | None = Field(default=None, ge=0, le=3)


def user_summary(user: User) -> dict:
    return {"id": user.id, "name": user.name, "mobile": user.mobile, "role": user.role}


def admin_user_summary(user: User) -> dict:
    return {**user_summary(user), "email": user.email, "school": user.school, "active": user.active,
            "createdAt": user.created_at, "lockedUntil": user.locked_until}


def create_session(db: Session, user: User) -> dict:
    refresh = new_refresh_token()
    now = datetime.now(UTC)
    db.add(RefreshToken(user_id=user.id, token_hash=hash_token(refresh),
                        expires_at=now + timedelta(days=settings.refresh_token_days)))
    db.commit()
    return {"accessToken": issue_access_token(user.id, user.role), "refreshToken": refresh,
            "user": user_summary(user)}


def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    try:
        claims = decode_access_token(token)
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(401, "Please log in again.") from exc
    user = db.get(User, user_id)
    if not user or not user.active:
        raise HTTPException(401, "Please log in again.")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "ADMIN":
        raise HTTPException(403, "Teacher access is required.")
    return user


def require_student(user: User = Depends(current_user)) -> User:
    if user.role != "STUDENT":
        raise HTTPException(403, "Student access is required.")
    return user


@app.get("/actuator/health")
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "UP"}


@app.get("/actuator/health/liveness")
def liveness() -> dict[str, str]:
    return {"status": "UP"}


@app.get("/actuator/health/readiness")
def readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(select(1))
    return {"status": "UP"}


@app.post("/auth/register", status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(User).where(User.mobile == data.mobile)):
        raise HTTPException(409, "That mobile number is already registered.")
    user = User(name=data.name.strip(), mobile=data.mobile, pin_hash=hash_pin(data.pin),
                email=data.email, school=data.school, role="STUDENT")
    db.add(user)
    db.commit()
    db.refresh(user)
    return create_session(db, user)


@app.post("/auth/login")
def login(data: Credentials, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.mobile == data.mobile))
    if not user:
        verify_pin(data.pin, DUMMY_PIN_HASH)
        raise HTTPException(401, "Wrong mobile number or PIN.")
    if not user.active:
        verify_pin(data.pin, user.pin_hash)
        raise HTTPException(401, "Wrong mobile number or PIN.")
    now = datetime.now(UTC)
    if user.locked_until and utc(user.locked_until) > now:
        raise HTTPException(429, "Too many wrong PINs. Please wait 15 minutes and try again.")
    if not verify_pin(data.pin, user.pin_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.failed_login_attempts = 0
            user.locked_until = now + timedelta(minutes=15)
        db.commit()
        raise HTTPException(401, "Wrong mobile number or PIN.")
    if user.pin_hash.startswith(("$2a$", "$2b$", "$2y$")):
        user.pin_hash = hash_pin(data.pin)
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    return create_session(db, user)


@app.post("/auth/refresh")
def refresh(data: RefreshRequest, db: Session = Depends(get_db)) -> dict:
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(data.refresh_token)))
    now = datetime.now(UTC)
    if not stored or stored.revoked_at or stored.expires_at <= now:
        raise HTTPException(401, "Please log in again.")
    user = db.get(User, stored.user_id)
    if not user or not user.active:
        raise HTTPException(401, "Please log in again.")
    stored.revoked_at = now
    db.commit()
    return create_session(db, user)


@app.post("/auth/logout", status_code=204)
def logout(data: RefreshRequest, db: Session = Depends(get_db)) -> None:
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(data.refresh_token)))
    if stored and not stored.revoked_at:
        stored.revoked_at = datetime.now(UTC)
        db.commit()


@app.get("/me")
def get_me(user: User = Depends(current_user)) -> dict:
    return user_summary(user)


@app.get("/admin/users")
def list_users(q: str | None = None, active: bool | None = None, page: int = 0, size: int = 20,
               _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    if page < 0 or not 1 <= size <= 100:
        raise HTTPException(422, "Page or page size is outside the allowed range.")
    statement = select(User).where(User.role == "STUDENT").order_by(User.created_at.desc())
    if q:
        pattern = f"%{q}%"
        statement = statement.where(or_(User.name.ilike(pattern), User.mobile.ilike(pattern)))
    if active is not None:
        statement = statement.where(User.active.is_(active))
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    users = list(db.scalars(statement.offset(page * size).limit(size)))
    return {"content": [admin_user_summary(user) for user in users], "page": page, "size": size,
            "totalElements": total, "totalPages": (total + size - 1) // size}


@app.patch("/admin/users/{user_id}")
def set_user_active(user_id: int, data: UserActiveRequest, _: User = Depends(require_admin),
                    db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if not user or user.role != "STUDENT":
        raise HTTPException(404, "Student not found.")
    user.active = data.active
    if not data.active:
        db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
    db.commit()
    return admin_user_summary(user)


@app.post("/admin/users/{user_id}/reset-pin")
def reset_user_pin(user_id: int, data: ResetPinRequest, _: User = Depends(require_admin),
                   db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if not user or user.role != "STUDENT":
        raise HTTPException(404, "Student not found.")
    user.pin_hash = hash_pin(data.pin)
    user.failed_login_attempts = 0
    user.locked_until = None
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
    db.commit()
    return admin_user_summary(user)


@app.post("/admin/admins", status_code=201)
def create_admin(data: CreateAdminRequest, _: User = Depends(require_admin),
                 db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(User).where(User.mobile == data.mobile)):
        raise HTTPException(409, "That mobile number is already registered.")
    user = User(name=data.name.strip(), mobile=data.mobile, pin_hash=hash_pin(data.pin), role="ADMIN")
    db.add(user)
    db.commit()
    db.refresh(user)
    return admin_user_summary(user)


def group_detail(db: Session, group: StudentGroup) -> dict:
    members = sorted((member for member in group.members if member.role == "STUDENT"),
                     key=lambda member: member.name.casefold())
    return {"id": group.id, "name": group.name,
            "members": [admin_user_summary(member) for member in members], "createdAt": group.created_at}


@app.get("/admin/groups")
def list_groups(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    groups = list(db.scalars(select(StudentGroup).order_by(StudentGroup.name)))
    return [{"id": group.id, "name": group.name,
             "memberCount": sum(member.role == "STUDENT" for member in group.members),
             "createdAt": group.created_at} for group in groups]


@app.get("/admin/groups/{group_id}")
def get_group(group_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    group = db.get(StudentGroup, group_id)
    if not group:
        raise HTTPException(404, "Group not found.")
    return group_detail(db, group)


@app.post("/admin/groups", status_code=201)
def create_group(data: GroupRequest, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    name = data.name.strip()
    if db.scalar(select(StudentGroup).where(func.lower(StudentGroup.name) == name.lower())):
        raise HTTPException(409, "A group with that name already exists.")
    group = StudentGroup(name=name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group_detail(db, group)


@app.put("/admin/groups/{group_id}")
def rename_group(group_id: int, data: GroupRequest, _: User = Depends(require_admin),
                 db: Session = Depends(get_db)) -> dict:
    group = db.get(StudentGroup, group_id)
    if not group:
        raise HTTPException(404, "Group not found.")
    group.name = data.name.strip()
    db.commit()
    return group_detail(db, group)


@app.delete("/admin/groups/{group_id}", status_code=204)
def delete_group(group_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    group = db.get(StudentGroup, group_id)
    if not group:
        raise HTTPException(404, "Group not found.")
    db.delete(group)
    db.commit()
    return Response(status_code=204)


@app.post("/admin/groups/{group_id}/members")
def add_group_members(group_id: int, data: GroupMembersRequest, _: User = Depends(require_admin),
                      db: Session = Depends(get_db)) -> dict:
    group = db.get(StudentGroup, group_id)
    students = list(db.scalars(select(User).where(User.id.in_(data.student_ids), User.role == "STUDENT")))
    if not group or len(students) != len(set(data.student_ids)):
        raise HTTPException(404, "Group or student not found.")
    known = {member.id for member in group.members}
    group.members.extend(student for student in students if student.id not in known)
    db.commit()
    return group_detail(db, group)


@app.delete("/admin/groups/{group_id}/members/{student_id}")
def remove_group_member(group_id: int, student_id: int, _: User = Depends(require_admin),
                        db: Session = Depends(get_db)) -> dict:
    group = db.get(StudentGroup, group_id)
    student = db.get(User, student_id)
    if not group or not student or student not in group.members:
        raise HTTPException(404, "Group member not found.")
    group.members.remove(student)
    db.commit()
    return group_detail(db, group)


def question_response(question: Question) -> dict:
    return {"id": question.id, "text": question.text, "options": json.loads(question.options_json),
            "correctOption": question.correct_option, "timeLimitSeconds": question.time_limit_seconds,
            "createdAt": question.created_at, "updatedAt": question.created_at}


@app.get("/admin/questions")
def list_questions(q: str | None = None, page: int = 0, size: int = 20,
                   _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    if page < 0 or not 1 <= size <= 100:
        raise HTTPException(422, "Page or page size is outside the allowed range.")
    statement = select(Question).order_by(Question.created_at.desc())
    if q:
        statement = statement.where(Question.text.ilike(f"%{q}%"))
    items = list(db.scalars(statement.offset(page * size).limit(size)))
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    return {"content": [question_response(item) for item in items], "page": page, "size": size,
            "totalElements": total, "totalPages": (total + size - 1) // size}


@app.get("/admin/questions/{question_id}")
def get_question(question_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(404, "Question not found.")
    return question_response(question)


@app.post("/admin/questions", status_code=201)
def create_question(data: QuestionRequest, _: User = Depends(require_admin),
                    db: Session = Depends(get_db)) -> dict:
    if len({option.strip().casefold() for option in data.options}) != 4:
        raise HTTPException(422, "All four answers must be different.")
    question = Question(text=data.text.strip(), options_json=json.dumps(data.options),
                        correct_option=data.correct_option, time_limit_seconds=data.time_limit_seconds)
    db.add(question)
    db.commit()
    db.refresh(question)
    return question_response(question)


@app.put("/admin/questions/{question_id}")
def update_question(question_id: int, data: QuestionRequest, _: User = Depends(require_admin),
                    db: Session = Depends(get_db)) -> dict:
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(404, "Question not found.")
    if len({option.strip().casefold() for option in data.options}) != 4:
        raise HTTPException(422, "All four answers must be different.")
    question.text = data.text.strip()
    question.options_json = json.dumps(data.options)
    question.correct_option = data.correct_option
    question.time_limit_seconds = data.time_limit_seconds
    db.commit()
    return question_response(question)


@app.delete("/admin/questions/{question_id}", status_code=204)
def delete_question(question_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(404, "Question not found.")
    used = db.scalar(select(QuizQuestion).where(QuizQuestion.question_id == question_id))
    if used:
        raise HTTPException(409, "Remove this question from its quizzes before deleting it.")
    db.delete(question)
    db.commit()
    return Response(status_code=204)


def quiz_response(db: Session, quiz: Quiz) -> dict:
    pairs = list(db.scalars(select(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id)
                            .order_by(QuizQuestion.position)))
    questions = [db.get(Question, pair.question_id) for pair in pairs]
    return {"id": quiz.id, "title": quiz.title, "totalTimeLimitSeconds": quiz.total_time_limit_seconds,
            "showAnswers": quiz.show_answers, "questionTimeSeconds": sum(q.time_limit_seconds for q in questions),
            "questionCount": len(questions), "questions": [question_response(q) for q in questions],
            "createdAt": quiz.created_at, "updatedAt": quiz.created_at}


@app.get("/admin/quizzes")
def list_quizzes(q: str | None = None, page: int = 0, size: int = 20,
                 _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    if page < 0 or not 1 <= size <= 100:
        raise HTTPException(422, "Page or page size is outside the allowed range.")
    statement = select(Quiz).order_by(Quiz.created_at.desc())
    if q:
        statement = statement.where(Quiz.title.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    items = list(db.scalars(statement.offset(page * size).limit(size)))
    return {"content": [quiz_response(db, quiz) for quiz in items], "page": page, "size": size,
            "totalElements": total, "totalPages": (total + size - 1) // size}


@app.get("/admin/quizzes/{quiz_id}")
def get_quiz(quiz_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz not found.")
    return quiz_response(db, quiz)


@app.post("/admin/quizzes", status_code=201)
def create_quiz(data: QuizRequest, _: User = Depends(require_admin),
                db: Session = Depends(get_db)) -> dict:
    questions = [db.get(Question, question_id) for question_id in data.question_ids]
    if any(question is None for question in questions) or len(set(data.question_ids)) != len(data.question_ids):
        raise HTTPException(422, "Choose valid, unique questions.")
    quiz = Quiz(title=data.title.strip(), total_time_limit_seconds=data.total_time_limit_seconds,
                show_answers=data.show_answers)
    db.add(quiz)
    db.flush()
    db.add_all(QuizQuestion(quiz_id=quiz.id, position=index, question_id=question_id)
               for index, question_id in enumerate(data.question_ids, 1))
    db.commit()
    db.refresh(quiz)
    return quiz_response(db, quiz)


@app.put("/admin/quizzes/{quiz_id}")
def update_quiz(quiz_id: int, data: QuizRequest, _: User = Depends(require_admin),
                db: Session = Depends(get_db)) -> dict:
    quiz = db.get(Quiz, quiz_id)
    questions = [db.get(Question, question_id) for question_id in data.question_ids]
    if not quiz:
        raise HTTPException(404, "Quiz not found.")
    if any(question is None for question in questions) or len(set(data.question_ids)) != len(data.question_ids):
        raise HTTPException(422, "Choose valid, unique questions.")
    quiz.title = data.title.strip()
    quiz.total_time_limit_seconds = data.total_time_limit_seconds
    quiz.show_answers = data.show_answers
    db.execute(delete(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id))
    db.flush()
    db.add_all(QuizQuestion(quiz_id=quiz_id, position=index, question_id=question_id)
               for index, question_id in enumerate(data.question_ids, 1))
    db.commit()
    return quiz_response(db, quiz)


@app.delete("/admin/quizzes/{quiz_id}", status_code=204)
def delete_quiz(quiz_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz not found.")
    db.delete(quiz)
    db.commit()
    return Response(status_code=204)


def assignment_response(db: Session, assignment: Assignment) -> dict:
    student = db.get(User, assignment.student_id) if assignment.student_id else None
    group = db.get(StudentGroup, assignment.group_id) if assignment.group_id else None
    return {"id": assignment.id, "targetType": assignment.target_type,
            "studentId": student.id if student else None, "studentName": student.name if student else None,
            "studentMobile": student.mobile if student else None,
            "groupId": group.id if group else None, "groupName": group.name if group else None,
            "assignedAt": assignment.assigned_at, "dueAt": assignment.due_at}


@app.get("/admin/quizzes/{quiz_id}/assignments")
def list_assignments(quiz_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    if not db.get(Quiz, quiz_id):
        raise HTTPException(404, "Quiz not found.")
    rows = db.scalars(select(Assignment).where(Assignment.quiz_id == quiz_id)
                      .order_by(Assignment.assigned_at.desc()))
    return [assignment_response(db, row) for row in rows]


@app.post("/admin/quizzes/{quiz_id}/assignments", status_code=201)
def assign_quiz(quiz_id: int, data: AssignmentRequest, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)) -> dict:
    if not db.get(Quiz, quiz_id):
        raise HTTPException(404, "Quiz not found.")
    student_id = data.student_id if data.target_type == "STUDENT" else None
    group_id = data.group_id if data.target_type == "GROUP" else None
    if (data.target_type == "STUDENT" and (not student_id or not db.get(User, student_id)
                                            or db.get(User, student_id).role != "STUDENT")):
        raise HTTPException(422, "Choose a student for this assignment.")
    if data.target_type == "GROUP" and (not group_id or not db.get(StudentGroup, group_id)):
        raise HTTPException(422, "Choose a group for this assignment.")
    query = select(Assignment).where(Assignment.quiz_id == quiz_id,
                                     Assignment.target_type == data.target_type)
    if student_id:
        query = query.where(Assignment.student_id == student_id)
    if group_id:
        query = query.where(Assignment.group_id == group_id)
    existing = db.scalar(query)
    if existing:
        existing.due_at = data.due_at
        db.commit()
        return assignment_response(db, existing)
    assignment = Assignment(quiz_id=quiz_id, target_type=data.target_type, student_id=student_id,
                            group_id=group_id, due_at=data.due_at, assigned_by=admin.id)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment_response(db, assignment)


@app.delete("/admin/quizzes/{quiz_id}/assignments/{assignment_id}", status_code=204)
def remove_assignment(quiz_id: int, assignment_id: int, _: User = Depends(require_admin),
                      db: Session = Depends(get_db)) -> Response:
    assignment = db.get(Assignment, assignment_id)
    if not assignment or assignment.quiz_id != quiz_id:
        raise HTTPException(404, "Assignment not found.")
    db.delete(assignment)
    db.commit()
    return Response(status_code=204)


def assignment_for(db: Session, student_id: int, quiz_id: int) -> Assignment | None:
    group_ids = select(group_members.c.group_id).where(group_members.c.student_id == student_id)
    return db.scalar(select(Assignment).where(
        Assignment.quiz_id == quiz_id,
        or_(Assignment.target_type == "ALL",
            and_(Assignment.target_type == "STUDENT", Assignment.student_id == student_id),
            and_(Assignment.target_type == "GROUP", Assignment.group_id.in_(group_ids))),
    ).order_by(Assignment.assigned_at.desc()))


def attempt_questions(db: Session, attempt_id: int) -> list[AttemptQuestion]:
    return list(db.scalars(select(AttemptQuestion).where(AttemptQuestion.attempt_id == attempt_id)
                           .order_by(AttemptQuestion.position)))


def finish_attempt(attempt: Attempt, now: datetime, reason: str) -> None:
    attempt.status = "COMPLETED"
    attempt.finished_at = now
    attempt.finish_reason = reason


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def attempt_state(db: Session, attempt: Attempt, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    questions = attempt_questions(db, attempt.id)
    current = next((question for question in questions if question.answered_at is None), None)
    if attempt.status == "IN_PROGRESS" and attempt.deadline_at and now >= utc(attempt.deadline_at):
        finish_attempt(attempt, now, "TIME_UP")
        current = None
    elif current and current.served_at:
        expires_at = utc(current.served_at) + timedelta(seconds=current.time_limit_seconds)
        if now >= expires_at:
            current.answered_at = expires_at
            following = next((question for question in questions
                              if question.position > current.position and question.answered_at is None), None)
            if following:
                following.served_at = expires_at
                current = following
            else:
                finish_attempt(attempt, expires_at, "ALL_ANSWERED")
                current = None
    elif current:
        current.served_at = now
    if attempt.status == "IN_PROGRESS" and current is None:
        finish_attempt(attempt, now, "ALL_ANSWERED")
    if attempt.status == "COMPLETED":
        db.commit()
        return {"attemptId": attempt.id, "quizTitle": attempt.quiz_title, "status": attempt.status,
                "questionCount": attempt.question_count, "question": None, "quizSecondsLeft": 0 if attempt.finish_reason == "TIME_UP" else None,
                "result": {"score": attempt.score, "questionCount": attempt.question_count,
                           "percentage": round(attempt.score * 100 / max(1, attempt.question_count)),
                           "finishReason": attempt.finish_reason}}
    if current is None:
        current = next((question for question in questions if question.answered_at is None), None)
        if current and current.served_at is None:
            current.served_at = now
    db.commit()
    seconds_left = max(0, math.ceil((utc(current.served_at) + timedelta(seconds=current.time_limit_seconds) - now).total_seconds())) if current and current.served_at else 0
    quiz_seconds_left = max(0, math.ceil((utc(attempt.deadline_at) - now).total_seconds())) if attempt.deadline_at else None
    public_question = None if current is None else {
        "position": current.position, "text": current.text, "options": json.loads(current.options_json),
        "timeLimitSeconds": current.time_limit_seconds, "secondsLeft": seconds_left,
    }
    return {"attemptId": attempt.id, "quizTitle": attempt.quiz_title, "status": attempt.status,
            "questionCount": attempt.question_count, "question": public_question,
            "quizSecondsLeft": quiz_seconds_left, "result": None}


def student_quiz_response(db: Session, student: User, quiz: Quiz, assignment: Assignment) -> dict:
    questions = list(db.scalars(select(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id)
                                .order_by(QuizQuestion.position)))
    attempt = db.scalar(select(Attempt).where(Attempt.quiz_id == quiz.id,
                                              Attempt.student_id == student.id))
    status = attempt.status if attempt else "NEW"
    return {"quizId": quiz.id, "title": quiz.title, "questionCount": len(questions),
            "questionTimeSeconds": sum((db.get(Question, item.question_id).time_limit_seconds
                                         for item in questions), 0),
            "totalTimeLimitSeconds": quiz.total_time_limit_seconds,
            "assignedAt": assignment.assigned_at, "dueAt": assignment.due_at,
            "status": status, "attemptId": attempt.id if attempt else None,
            "score": attempt.score if attempt and attempt.status == "COMPLETED" else None}


@app.get("/me/quizzes")
def list_my_quizzes(student: User = Depends(require_student), db: Session = Depends(get_db)) -> list[dict]:
    quizzes = list(db.scalars(select(Quiz).order_by(Quiz.created_at.desc())))
    rows = []
    for quiz in quizzes:
        assignment = assignment_for(db, student.id, quiz.id)
        if assignment:
            rows.append(student_quiz_response(db, student, quiz, assignment))
    return rows


@app.get("/me/quizzes/{quiz_id}")
def get_my_quiz(quiz_id: int, student: User = Depends(require_student), db: Session = Depends(get_db)) -> dict:
    quiz = db.get(Quiz, quiz_id)
    assignment = assignment_for(db, student.id, quiz_id)
    if not quiz or not assignment:
        raise HTTPException(404, "Quiz not found.")
    return student_quiz_response(db, student, quiz, assignment)


@app.post("/me/quizzes/{quiz_id}/attempt")
def start_attempt(quiz_id: int, student: User = Depends(require_student), db: Session = Depends(get_db)) -> dict:
    quiz = db.get(Quiz, quiz_id)
    assignment = assignment_for(db, student.id, quiz_id)
    if not quiz or not assignment:
        raise HTTPException(404, "Quiz not found.")
    attempt = db.scalar(select(Attempt).where(Attempt.quiz_id == quiz_id, Attempt.student_id == student.id))
    if attempt:
        return attempt_state(db, attempt)
    pairs = list(db.scalars(select(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id)
                            .order_by(QuizQuestion.position)))
    if not pairs:
        raise HTTPException(409, "This quiz does not have any questions yet.")
    now = datetime.now(UTC)
    deadline = now + timedelta(seconds=quiz.total_time_limit_seconds) if quiz.total_time_limit_seconds else None
    attempt = Attempt(quiz_id=quiz.id, student_id=student.id, quiz_title=quiz.title,
                      total_time_limit_seconds=quiz.total_time_limit_seconds, show_answers=quiz.show_answers,
                      due_at=assignment.due_at, late=bool(assignment.due_at and utc(assignment.due_at) < now),
                      started_at=now, deadline_at=deadline, question_count=len(pairs))
    db.add(attempt)
    db.flush()
    for index, pair in enumerate(pairs, 1):
        source = db.get(Question, pair.question_id)
        db.add(AttemptQuestion(attempt_id=attempt.id, position=index, question_id=source.id,
                               text=source.text, options_json=source.options_json,
                               correct_option=source.correct_option, time_limit_seconds=source.time_limit_seconds,
                               served_at=now if index == 1 else None))
    db.commit()
    db.refresh(attempt)
    return attempt_state(db, attempt, now)


def owned_attempt(db: Session, attempt_id: int, student_id: int) -> Attempt:
    attempt = db.get(Attempt, attempt_id)
    if not attempt or attempt.student_id != student_id:
        raise HTTPException(404, "Attempt not found.")
    return attempt


@app.get("/me/attempts/{attempt_id}")
def get_attempt(attempt_id: int, student: User = Depends(require_student), db: Session = Depends(get_db)) -> dict:
    return attempt_state(db, owned_attempt(db, attempt_id, student.id))


@app.post("/me/attempts/{attempt_id}/answers")
def submit_answer(attempt_id: int, data: AnswerRequest, student: User = Depends(require_student),
                  db: Session = Depends(get_db)) -> dict:
    attempt = owned_attempt(db, attempt_id, student.id)
    state = attempt_state(db, attempt)
    if state["status"] == "COMPLETED":
        return state
    current = next((item for item in attempt_questions(db, attempt.id) if item.answered_at is None), None)
    if not current or current.position != data.position:
        raise HTTPException(409, "This question is no longer open.")
    now = datetime.now(UTC)
    closes_at = utc(current.served_at) + timedelta(seconds=current.time_limit_seconds)
    in_time = now <= closes_at and (not attempt.deadline_at or now <= utc(attempt.deadline_at))
    selected = data.selected_option if in_time else None
    current.selected_option = selected
    current.correct = selected is not None and selected == current.correct_option
    current.answered_at = now if in_time else closes_at
    if current.correct:
        attempt.score += 1
    following = next((item for item in attempt_questions(db, attempt.id)
                      if item.position > current.position and item.answered_at is None), None)
    if following:
        following.served_at = current.answered_at
    else:
        finish_attempt(attempt, current.answered_at, "ALL_ANSWERED")
    db.commit()
    return attempt_state(db, attempt, current.answered_at)


def result_outcome(question: AttemptQuestion) -> str:
    if question.selected_option is None:
        return "NO_ANSWER" if question.answered_at else "NOT_REACHED"
    return "CORRECT" if question.correct else "WRONG"


def result_question(question: AttemptQuestion, detail: bool = False) -> dict:
    data = {"position": question.position, "text": question.text,
            "options": json.loads(question.options_json), "selectedOption": question.selected_option,
            "correctOption": question.correct_option, "outcome": result_outcome(question)}
    if detail:
        data["timeLimitSeconds"] = question.time_limit_seconds
        data["secondsTaken"] = (max(0, round((question.answered_at - question.served_at).total_seconds()))
                                if question.answered_at and question.served_at else None)
    return data


def attempt_row(db: Session, attempt: Attempt) -> dict:
    student = db.get(User, attempt.student_id)
    return {"id": attempt.id, "studentId": student.id, "studentName": student.name,
            "studentMobile": student.mobile, "quizId": attempt.quiz_id, "quizTitle": attempt.quiz_title,
            "status": attempt.status, "score": attempt.score, "questionCount": attempt.question_count,
            "percentage": round(attempt.score * 100 / max(1, attempt.question_count)),
            "startedAt": attempt.started_at, "finishedAt": attempt.finished_at, "late": attempt.late}


def safe_csv_cell(value: object) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


@app.get("/me/results")
def list_my_results(student: User = Depends(require_student), db: Session = Depends(get_db)) -> list[dict]:
    attempts = db.scalars(select(Attempt).where(Attempt.student_id == student.id,
                                                Attempt.status == "COMPLETED")
                          .order_by(Attempt.finished_at.desc()))
    return [{"attemptId": item.id, "quizId": item.quiz_id, "quizTitle": item.quiz_title,
             "finishedAt": item.finished_at, "score": item.score, "questionCount": item.question_count,
             "percentage": round(item.score * 100 / max(1, item.question_count))} for item in attempts]


@app.get("/me/results/{attempt_id}")
def get_my_review(attempt_id: int, student: User = Depends(require_student), db: Session = Depends(get_db)) -> dict:
    attempt = owned_attempt(db, attempt_id, student.id)
    questions = attempt_questions(db, attempt.id) if attempt.show_answers else []
    return {"attemptId": attempt.id, "quizId": attempt.quiz_id, "quizTitle": attempt.quiz_title,
            "finishedAt": attempt.finished_at, "score": attempt.score, "questionCount": attempt.question_count,
            "percentage": round(attempt.score * 100 / max(1, attempt.question_count)),
            "finishReason": attempt.finish_reason, "answersShown": attempt.show_answers,
            "questions": [result_question(question) for question in questions]}


@app.get("/admin/attempts")
def list_attempts(quiz_id: int | None = None, q: str | None = None, page: int = 0, size: int = 20,
                  _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    if page < 0 or not 1 <= size <= 100:
        raise HTTPException(422, "Page or page size is outside the allowed range.")
    statement = select(Attempt).join(User, Attempt.student_id == User.id).order_by(Attempt.started_at.desc())
    if quiz_id:
        statement = statement.where(Attempt.quiz_id == quiz_id)
    if q:
        pattern = f"%{q}%"
        statement = statement.where(or_(User.name.ilike(pattern), User.mobile.ilike(pattern)))
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    items = list(db.scalars(statement.offset(page * size).limit(size)))
    return {"content": [attempt_row(db, item) for item in items], "page": page, "size": size,
            "totalElements": total, "totalPages": (total + size - 1) // size}


@app.get("/admin/attempts/{attempt_id:int}")
def get_attempt_detail(attempt_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    attempt = db.get(Attempt, attempt_id)
    if not attempt:
        raise HTTPException(404, "Attempt not found.")
    student = db.get(User, attempt.student_id)
    return {"attempt": attempt_row(db, attempt), "studentSchool": student.school,
            "dueAt": attempt.due_at, "totalTimeLimitSeconds": attempt.total_time_limit_seconds,
            "finishReason": attempt.finish_reason,
            "questions": [result_question(question, True) for question in attempt_questions(db, attempt.id)]}


@app.get("/admin/attempts/export")
def export_attempts(quiz_id: int | None = None, q: str | None = None,
                    _: User = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    statement = select(Attempt).join(User, Attempt.student_id == User.id).order_by(Attempt.started_at.desc())
    if quiz_id:
        statement = statement.where(Attempt.quiz_id == quiz_id)
    if q:
        pattern = f"%{q}%"
        statement = statement.where(or_(User.name.ilike(pattern), User.mobile.ilike(pattern)))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student", "Mobile", "School", "Quiz", "Score", "Questions", "Percentage",
                     "Started at", "Finished at", "Late"])
    for attempt in db.scalars(statement):
        student = db.get(User, attempt.student_id)
        writer.writerow([safe_csv_cell(student.name), safe_csv_cell(student.mobile),
                 safe_csv_cell(student.school), safe_csv_cell(attempt.quiz_title),
                 attempt.score, attempt.question_count,
                 round(attempt.score * 100 / max(1, attempt.question_count)),
                 attempt.started_at.isoformat(),
                 attempt.finished_at.isoformat() if attempt.finished_at else "", attempt.late])
    return Response(output.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=quiz-results.csv"})


class RoomHub:
    def __init__(self) -> None:
        self.connections: dict[str, dict[int, WebSocket]] = {}
        self.sessions: dict[str, dict] = {}
        self.lock = asyncio.Lock()

    async def connect(self, code: str, user_id: int, socket: WebSocket) -> int:
        await socket.accept(subprotocol="bearer")
        async with self.lock:
            self.connections.setdefault(code, {})[user_id] = socket
            return len(self.connections[code])

    async def disconnect(self, code: str, user_id: int) -> int:
        async with self.lock:
            members = self.connections.get(code, {})
            members.pop(user_id, None)
            if not members:
                self.connections.pop(code, None)
            return len(members)

    async def broadcast(self, code: str, payload: dict) -> None:
        members = self.connections.get(code, {})
        await asyncio.gather(*(ws.send_json(payload) for ws in members.values()), return_exceptions=True)

    async def begin(self, code: str, host_id: int, questions: list[dict], total_time_limit_seconds: int | None) -> None:
        self.sessions[code] = {"hostId": host_id, "questions": questions, "index": 0,
                               "answered": set(), "scores": {}, "lock": asyncio.Lock(), "complete": False,
                               "quizDeadline": (asyncio.get_running_loop().time() + total_time_limit_seconds
                                                if total_time_limit_seconds else None)}
        await self.broadcast(code, {"type": "started"})
        await self.publish_question(code)

    async def publish_question(self, code: str) -> None:
        session = self.sessions.get(code)
        if not session or session["complete"]:
            return
        index = session["index"]
        loop = asyncio.get_running_loop()
        if session["quizDeadline"] is not None and loop.time() >= session["quizDeadline"]:
            index = len(session["questions"])
            session["index"] = index
        if index >= len(session["questions"]):
            session["complete"] = True
            scores = sorted(session["scores"].values(), key=lambda row: (-row["score"], row["name"].casefold()))
            await self.broadcast(code, {"type": "finished", "scores": scores})
            with SessionLocal() as db:
                room = db.scalar(select(QuizRoom).where(QuizRoom.code == code))
                if room:
                    room.status = "COMPLETED"
                    db.commit()
            return
        question = session["questions"][index]
        session["answered"] = set()
        question_seconds = question["timeLimitSeconds"]
        if session["quizDeadline"] is not None:
            question_seconds = min(question_seconds, max(0, math.ceil(session["quizDeadline"] - loop.time())))
        session["deadline"] = loop.time() + question_seconds
        await self.broadcast(code, {"type": "question", "position": index + 1,
                                    "questionCount": len(session["questions"]), "text": question["text"],
                                    "options": question["options"],
                                    "timeLimitSeconds": question["timeLimitSeconds"],
                                    "secondsLeft": question_seconds})
        session["timer"] = asyncio.create_task(self.timeout(code, index, question_seconds))

    async def timeout(self, code: str, index: int, seconds: int) -> None:
        await asyncio.sleep(seconds)
        await self.advance(code, index)

    async def advance(self, code: str, expected_index: int) -> None:
        session = self.sessions.get(code)
        if not session or session["complete"] or session["index"] != expected_index:
            return
        if session["quizDeadline"] is not None and asyncio.get_running_loop().time() >= session["quizDeadline"]:
            session["index"] = len(session["questions"])
            await self.publish_question(code)
            return
        session["index"] += 1
        await self.publish_question(code)

    async def answer(self, code: str, user_id: int, name: str, option: object,
                     socket: WebSocket) -> None:
        session = self.sessions.get(code)
        if not session or session["complete"]:
            await socket.send_json({"type": "error", "detail": "This session is not taking answers."})
            return
        advance = False
        async with session["lock"]:
            index = session["index"]
            if user_id == session["hostId"]:
                await socket.send_json({"type": "error", "detail": "The teacher cannot answer for students."})
                return
            if user_id in session["answered"]:
                await socket.send_json({"type": "error", "detail": "Your answer was already received."})
                return
            if not isinstance(option, int) or not 0 <= option <= 3:
                await socket.send_json({"type": "error", "detail": "Choose one of the four answers."})
                return
            if asyncio.get_running_loop().time() >= session["deadline"]:
                await socket.send_json({"type": "error", "detail": "Time is up for this question."})
                return
            question = session["questions"][index]
            correct = option == question["correctOption"]
            score = session["scores"].setdefault(user_id, {"userId": user_id, "name": name, "score": 0})
            if correct:
                score["score"] += 1
            session["answered"].add(user_id)
            await socket.send_json({"type": "answer_result", "correct": correct})
            active_count = sum(member_id != session["hostId"]
                               for member_id in self.connections.get(code, {}))
            await self.broadcast(code, {"type": "answer_count", "answered": len(session["answered"]),
                                        "total": active_count})
            advance = active_count > 0 and len(session["answered"]) >= active_count
        if advance:
            await self.advance(code, session["index"])


room_hub = RoomHub()


@app.post("/admin/rooms", status_code=201)
def create_room(data: RoomRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    quiz = db.get(Quiz, data.quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz not found.")
    room = QuizRoom(code=secrets.token_urlsafe(4).replace("-", "").replace("_", "").upper()[:6],
                    quiz_id=quiz.id, host_id=admin.id)
    db.add(room)
    db.commit()
    db.refresh(room)
    return {"id": room.id, "code": room.code, "quizId": room.quiz_id,
            "quizTitle": quiz.title, "status": room.status}


@app.get("/admin/rooms/{code}")
def room_detail(code: str, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    room = db.scalar(select(QuizRoom).where(QuizRoom.code == code.upper()))
    if not room:
        raise HTTPException(404, "Room not found.")
    return {"id": room.id, "code": room.code, "quizId": room.quiz_id,
            "quizTitle": room.quiz.title, "status": room.status,
            "members": db.scalar(select(func.count()).select_from(QuizRoomMember)
                                  .where(QuizRoomMember.room_id == room.id)) or 0}


@app.post("/me/rooms/{code}/join")
def join_room(code: str, student: User = Depends(require_student), db: Session = Depends(get_db)) -> dict:
    room = db.scalar(select(QuizRoom).where(QuizRoom.code == code.upper()))
    if not room or room.status == "COMPLETED":
        raise HTTPException(404, "That quiz room is not open.")
    member = db.get(QuizRoomMember, (room.id, student.id))
    if room.status != "LOBBY" and not member:
        raise HTTPException(404, "That quiz room has already started.")
    if not member:
        db.add(QuizRoomMember(room_id=room.id, user_id=student.id))
        db.commit()
    return {"code": room.code, "quizTitle": room.quiz.title, "status": room.status}


@app.websocket("/ws/rooms/{code}")
async def room_socket(socket: WebSocket, code: str, db: Session = Depends(get_db)) -> None:
    try:
        protocols = [part.strip() for part in socket.headers.get("sec-websocket-protocol", "").split(",")]
        if len(protocols) != 2 or protocols[0] != "bearer":
            await socket.close(code=4401)
            return
        token = protocols[1]
        claims = decode_access_token(token)
        user = db.get(User, int(claims["sub"]))
        room = db.scalar(select(QuizRoom).where(QuizRoom.code == code.upper()))
        membership = db.get(QuizRoomMember, (room.id, user.id)) if room and user else None
        is_host = bool(room and user and room.host_id == user.id)
        if not user or not user.active or not room or (not membership and not is_host):
            await socket.close(code=4403)
            return
    except (jwt.PyJWTError, KeyError, ValueError):
        await socket.close(code=4401)
        return
    count = await room_hub.connect(room.code, user.id, socket)
    await room_hub.broadcast(room.code, {"type": "presence", "count": count})
    active = room_hub.sessions.get(room.code)
    if active and not active["complete"]:
        question = active["questions"][active["index"]]
        seconds_left = max(0, math.ceil(active["deadline"] - asyncio.get_running_loop().time()))
        await socket.send_json({"type": "question", "position": active["index"] + 1,
                                "questionCount": len(active["questions"]), "text": question["text"],
                                "options": question["options"], "timeLimitSeconds": question["timeLimitSeconds"],
                                "secondsLeft": seconds_left})
    try:
        while True:
            message = await socket.receive_json()
            if user.id == room.host_id and message.get("type") == "start":
                if room.status != "LOBBY":
                    await socket.send_json({"type": "error", "detail": "This room has already started."})
                    continue
                pairs = list(db.scalars(select(QuizQuestion).where(QuizQuestion.quiz_id == room.quiz_id)
                                        .order_by(QuizQuestion.position)))
                questions = []
                for pair in pairs:
                    question = db.get(Question, pair.question_id)
                    questions.append({"text": question.text, "options": json.loads(question.options_json),
                                      "correctOption": question.correct_option,
                                      "timeLimitSeconds": question.time_limit_seconds})
                if not questions:
                    await socket.send_json({"type": "error", "detail": "This quiz has no questions."})
                    continue
                room.status = "IN_PROGRESS"
                db.commit()
                await room_hub.begin(room.code, user.id, questions, room.quiz.total_time_limit_seconds)
            elif user.id != room.host_id and message.get("type") == "answer":
                await room_hub.answer(room.code, user.id, user.name, message.get("option"), socket)
            else:
                await socket.send_json({"type": "error", "detail": "That room action is not allowed."})
    except WebSocketDisconnect:
        count = await room_hub.disconnect(room.code, user.id)
        await room_hub.broadcast(room.code, {"type": "presence", "count": count})