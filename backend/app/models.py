from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

group_members = Table(
    "py_group_members",
    Base.metadata,
    Column("group_id", ForeignKey("py_student_groups.id", ondelete="CASCADE"), primary_key=True),
    Column("student_id", ForeignKey("py_users.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "py_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    mobile: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    pin_hash: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(254))
    school: Mapped[str | None] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(20), default="STUDENT")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RefreshToken(Base):
    __tablename__ = "py_refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("py_users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Question(Base):
    __tablename__ = "py_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(String(500))
    options_json: Mapped[str] = mapped_column(Text)
    correct_option: Mapped[int] = mapped_column(Integer)
    time_limit_seconds: Mapped[int] = mapped_column(Integer, default=60)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Quiz(Base):
    __tablename__ = "py_quizzes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    total_time_limit_seconds: Mapped[int | None] = mapped_column(Integer)
    show_answers: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QuizQuestion(Base):
    __tablename__ = "py_quiz_questions"

    quiz_id: Mapped[int] = mapped_column(ForeignKey("py_quizzes.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("py_questions.id"))


class StudentGroup(Base):
    __tablename__ = "py_student_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    members: Mapped[list[User]] = relationship(secondary=group_members)


class Assignment(Base):
    __tablename__ = "py_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("py_quizzes.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(10))
    student_id: Mapped[int | None] = mapped_column(ForeignKey("py_users.id", ondelete="CASCADE"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("py_student_groups.id", ondelete="CASCADE"))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by: Mapped[int] = mapped_column(ForeignKey("py_users.id"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Attempt(Base):
    __tablename__ = "py_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("py_quizzes.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("py_users.id", ondelete="CASCADE"))
    quiz_title: Mapped[str] = mapped_column(String(150))
    total_time_limit_seconds: Mapped[int | None] = mapped_column(Integer)
    show_answers: Mapped[bool] = mapped_column(Boolean)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    late: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(12), default="IN_PROGRESS")
    finish_reason: Mapped[str | None] = mapped_column(String(12))
    score: Mapped[int] = mapped_column(Integer, default=0)
    question_count: Mapped[int] = mapped_column(Integer)


class AttemptQuestion(Base):
    __tablename__ = "py_attempt_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("py_attempts.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    question_id: Mapped[int] = mapped_column(ForeignKey("py_questions.id"))
    text: Mapped[str] = mapped_column(String(500))
    options_json: Mapped[str] = mapped_column(Text)
    correct_option: Mapped[int] = mapped_column(Integer)
    time_limit_seconds: Mapped[int] = mapped_column(Integer)
    served_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    selected_option: Mapped[int | None] = mapped_column(Integer)
    correct: Mapped[bool] = mapped_column(Boolean, default=False)


class QuizRoom(Base):
    __tablename__ = "py_quiz_rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("py_quizzes.id", ondelete="CASCADE"))
    host_id: Mapped[int] = mapped_column(ForeignKey("py_users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="LOBBY")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    quiz: Mapped[Quiz] = relationship()


class QuizRoomMember(Base):
    __tablename__ = "py_quiz_room_members"

    room_id: Mapped[int] = mapped_column(ForeignKey("py_quiz_rooms.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("py_users.id", ondelete="CASCADE"), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())