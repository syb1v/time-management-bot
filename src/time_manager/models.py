from __future__ import annotations

from datetime import UTC, date, datetime, time
from enum import StrEnum

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, Time
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Persist UTC as naive values for SQLite and restore aware UTC values."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("UTCDateTime requires a timezone-aware value")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return value.replace(tzinfo=UTC) if value is not None else None


class Base(DeclarativeBase):
    pass


class Role(StrEnum):
    STUDENT = "student"
    OWNER = "owner"


class BlockKind(StrEnum):
    ROUTINE = "routine"
    SCHOOL = "school"
    TRAVEL = "travel"
    MEAL = "meal"
    REST = "rest"
    HOMEWORK = "homework"
    SOTKA = "sotka"


class BlockStatus(StrEnum):
    PLANNED = "planned"
    DONE = "done"
    PARTIAL = "partial"
    MOVED = "moved"
    SKIPPED = "skipped"


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    preferences: Mapped[UserPreferences] = relationship(back_populates="user", uselist=False)


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id"), primary_key=True)
    wake_time: Mapped[time] = mapped_column(Time, default=time(5, 45))
    bedtime: Mapped[time] = mapped_column(Time, default=time(21, 45))
    leave_0800: Mapped[time] = mapped_column(Time, default=time(7, 0))
    leave_0850: Mapped[time] = mapped_column(Time, default=time(7, 50))
    travel_home_minutes: Mapped[int] = mapped_column(Integer, default=45)
    breakfast_minutes: Mapped[int] = mapped_column(Integer, default=20)
    lunch_minutes: Mapped[int] = mapped_column(Integer, default=30)
    dinner_minutes: Mapped[int] = mapped_column(Integer, default=30)
    rest_minutes: Mapped[int] = mapped_column(Integer, default=45)
    focus_minutes: Mapped[int] = mapped_column(Integer, default=50)
    break_minutes: Mapped[int] = mapped_column(Integer, default=10)
    reminder_minutes: Mapped[int] = mapped_column(Integer, default=10)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    user: Mapped[User] = relationship(back_populates="preferences")


class SchoolLesson(Base):
    __tablename__ = "school_lessons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    weekday: Mapped[int] = mapped_column(Integer, index=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    subject: Mapped[str] = mapped_column(String(100))
    details: Mapped[str] = mapped_column(Text, default="")


class SotkaEvent(Base):
    __tablename__ = "sotka_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_key: Mapped[str] = mapped_column(String(160), unique=True)
    subject: Mapped[str] = mapped_column(String(100), index=True)
    available_on: Mapped[date] = mapped_column(Date, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="markdown")
    course_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    course_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lesson_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    lesson_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    viewed: Mapped[bool] = mapped_column(Boolean, default=False)
    homework_done: Mapped[bool] = mapped_column(Boolean, default=False)


class Dashboard(Base):
    __tablename__ = "dashboards"

    chat_id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[str] = mapped_column(String(16), default="text")


class DailyInput(Base):
    __tablename__ = "daily_inputs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    homework_minutes: Mapped[int] = mapped_column(Integer, default=0)
    sleep_hours: Mapped[float | None] = mapped_column(Float, nullable=True)


class PlanBlock(Base):
    __tablename__ = "plan_blocks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    start_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    end_at: Mapped[datetime] = mapped_column(UTCDateTime())
    kind: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(16), default=BlockStatus.PLANNED)
    completion_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    source_event_id: Mapped[int | None] = mapped_column(ForeignKey("sotka_events.id"))
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
