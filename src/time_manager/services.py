from __future__ import annotations

from datetime import UTC, date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .db import Database
from .importers import (
    SotkaEventData,
    next_subject_deadlines,
    parse_school_schedule,
    parse_sotka_schedule,
)
from .models import (
    BlockStatus,
    DailyInput,
    PlanBlock,
    SchoolLesson,
    SotkaEvent,
    UserPreferences,
)
from .planner import PlannerSettings, Workload, build_day_plan


class PlanningService:
    def __init__(self, database: Database, timezone: ZoneInfo) -> None:
        self.database = database
        self.timezone = timezone

    async def import_files(self, school_path: Path, sotka_path: Path, year: int) -> None:
        school = parse_school_schedule(school_path.read_text(encoding="utf-8"))
        sotka = parse_sotka_schedule(sotka_path.read_text(encoding="utf-8"), year)
        async with self.database.sessions() as session:
            await session.execute(delete(SchoolLesson))
            session.add_all(
                SchoolLesson(
                    weekday=item.weekday,
                    start_time=item.start,
                    end_time=item.end,
                    subject=item.subject,
                    details=item.details,
                )
                for item in school
            )
            await self._upsert_sotka(session, sotka, "markdown")
            await session.commit()

    async def import_school(self, school_path: Path) -> None:
        school = parse_school_schedule(school_path.read_text(encoding="utf-8"))
        async with self.database.sessions() as session:
            await session.execute(delete(SchoolLesson))
            session.add_all(
                SchoolLesson(
                    weekday=item.weekday,
                    start_time=item.start,
                    end_time=item.end,
                    subject=item.subject,
                    details=item.details,
                )
                for item in school
            )
            await session.commit()

    async def import_sotka_events(self, events: list[SotkaEventData], source: str = "api") -> None:
        if not events:
            raise ValueError("Sotka synchronization returned no selected course events")
        async with self.database.sessions() as session:
            if source == "api":
                obsolete = select(SotkaEvent.id).where(
                    (SotkaEvent.source == "markdown")
                    | ((SotkaEvent.source == "api") & SotkaEvent.course_id.is_(None))
                )
                await session.execute(
                    update(PlanBlock)
                    .where(PlanBlock.source_event_id.in_(obsolete))
                    .values(source_event_id=None)
                )
                await session.execute(
                    delete(SotkaEvent).where(
                        (SotkaEvent.source == "markdown")
                        | ((SotkaEvent.source == "api") & SotkaEvent.course_id.is_(None))
                    )
                )
            await self._upsert_sotka(session, events, source)
            await session.commit()

    async def has_sotka_events(self) -> bool:
        async with self.database.sessions() as session:
            return (await session.execute(select(SotkaEvent.id).limit(1))).first() is not None

    async def regenerate_range(self, user_id: int, start: date, days: int) -> None:
        for offset in range(days):
            await self.regenerate_day(user_id, start + timedelta(days=offset))

    @staticmethod
    async def _upsert_sotka(
        session: AsyncSession, events: list[SotkaEventData], source: str
    ) -> None:
        deadlines = next_subject_deadlines(events)
        for item in events:
            key = item.external_key or f"markdown:{item.subject}:{item.available_on.isoformat()}"
            existing = (
                await session.execute(select(SotkaEvent).where(SotkaEvent.external_key == key))
            ).scalar_one_or_none()
            values = {
                "subject": item.subject,
                "available_on": item.available_on,
                "duration_minutes": item.duration_minutes,
                "deadline": deadlines[id(item)],
                "source": source,
                "course_name": item.course_name,
                "course_id": item.course_id,
                "lesson_id": item.lesson_id,
                "starts_at": item.starts_at,
                "lesson_url": item.lesson_url,
                "viewed": item.viewed,
                "homework_done": item.homework_done,
            }
            if existing:
                for name, value in values.items():
                    setattr(existing, name, value)
            else:
                session.add(SotkaEvent(external_key=key, **values))

    async def set_homework(self, user_id: int, day: date, minutes: int) -> None:
        if not 0 <= minutes <= 12 * 60:
            raise ValueError("homework must be between 0 and 12 hours")
        async with self.database.sessions() as session:
            entry = (
                await session.execute(
                    select(DailyInput).where(DailyInput.user_id == user_id, DailyInput.day == day)
                )
            ).scalar_one_or_none()
            if entry:
                entry.homework_minutes = minutes
            else:
                session.add(DailyInput(user_id=user_id, day=day, homework_minutes=minutes))
            await session.commit()
        await self.regenerate_day(user_id, day)

    async def set_sleep(self, user_id: int, day: date, hours: float) -> None:
        if not 0 <= hours <= 16:
            raise ValueError("sleep must be between 0 and 16 hours")
        async with self.database.sessions() as session:
            entry = (
                await session.execute(
                    select(DailyInput).where(DailyInput.user_id == user_id, DailyInput.day == day)
                )
            ).scalar_one_or_none()
            if entry:
                entry.sleep_hours = hours
            else:
                session.add(DailyInput(user_id=user_id, day=day, sleep_hours=hours))
            await session.commit()

    async def regenerate_day(self, user_id: int, day: date) -> int:
        async with self.database.sessions() as session:
            preferences = await session.get(UserPreferences, user_id)
            if preferences is None:
                raise ValueError("user preferences not found")
            lessons = list(
                (
                    await session.execute(
                        select(SchoolLesson).where(SchoolLesson.weekday == day.weekday())
                    )
                ).scalars()
            )
            daily = (
                await session.execute(
                    select(DailyInput).where(DailyInput.user_id == user_id, DailyInput.day == day)
                )
            ).scalar_one_or_none()
            sotka_events = list(
                (
                    await session.execute(
                        select(SotkaEvent)
                        .where(SotkaEvent.available_on <= day, SotkaEvent.deadline >= day)
                        .order_by(SotkaEvent.deadline, SotkaEvent.available_on)
                    )
                ).scalars()
            )
            from .importers import SchoolEvent
            from .models import BlockKind

            sotka_workloads: list[Workload] = []
            for event in sotka_events:
                historical = list(
                    (
                        await session.execute(
                            select(PlanBlock).where(
                                PlanBlock.source_event_id == event.id,
                                PlanBlock.user_id == user_id,
                                PlanBlock.day < day,
                            )
                        )
                    ).scalars()
                )
                completed_minutes = sum(
                    round(
                        (block.end_at - block.start_at).total_seconds()
                        / 60
                        * block.completion_ratio
                    )
                    for block in historical
                )
                remaining = max(0, event.duration_minutes - completed_minutes)
                if remaining:
                    sotka_workloads.append(
                        Workload(BlockKind.SOTKA, f"Сотка: {event.subject}", remaining, event.id)
                    )

            result = build_day_plan(
                day,
                [
                    SchoolEvent(x.weekday, x.start_time, x.end_time, x.subject, x.details)
                    for x in lessons
                ],
                daily.homework_minutes if daily else 0,
                sotka_workloads,
                PlannerSettings(
                    wake_time=preferences.wake_time,
                    bedtime=preferences.bedtime,
                    leave_0800=preferences.leave_0800,
                    leave_0850=preferences.leave_0850,
                    travel_home_minutes=preferences.travel_home_minutes,
                    breakfast_minutes=preferences.breakfast_minutes,
                    lunch_minutes=preferences.lunch_minutes,
                    dinner_minutes=preferences.dinner_minutes,
                    rest_minutes=preferences.rest_minutes,
                    focus_minutes=preferences.focus_minutes,
                    break_minutes=preferences.break_minutes,
                ),
                self.timezone,
            )
            old_blocks = list(
                (
                    await session.execute(
                        select(PlanBlock).where(PlanBlock.user_id == user_id, PlanBlock.day == day)
                    )
                ).scalars()
            )
            completed = {
                (b.kind, b.title, b.start_at): (b.status, b.completion_ratio) for b in old_blocks
            }
            await session.execute(
                delete(PlanBlock).where(PlanBlock.user_id == user_id, PlanBlock.day == day)
            )
            for block in result.blocks:
                key = (block.kind, block.title, block.start.astimezone(UTC))
                status, ratio = completed.get(key, (BlockStatus.PLANNED, 0.0))
                session.add(
                    PlanBlock(
                        user_id=user_id,
                        day=day,
                        start_at=block.start,
                        end_at=block.end,
                        kind=block.kind,
                        title=block.title,
                        source_event_id=block.source_event_id,
                        status=status,
                        completion_ratio=ratio,
                    )
                )
            await session.commit()
            return result.unscheduled_minutes

    async def ensure_week(self, user_id: int, start: date) -> None:
        for offset in range(7):
            day = start + timedelta(days=offset)
            async with self.database.sessions() as session:
                exists = (
                    await session.execute(
                        select(PlanBlock.id).where(
                            PlanBlock.user_id == user_id, PlanBlock.day == day
                        )
                    )
                ).first()
            if not exists:
                await self.regenerate_day(user_id, day)

    async def blocks(self, user_id: int, day: date) -> list[PlanBlock]:
        async with self.database.sessions() as session:
            return list(
                (
                    await session.execute(
                        select(PlanBlock)
                        .where(PlanBlock.user_id == user_id, PlanBlock.day == day)
                        .order_by(PlanBlock.start_at)
                    )
                ).scalars()
            )

    async def sotka_events(self, start: date, end: date) -> list[SotkaEvent]:
        async with self.database.sessions() as session:
            return list(
                (
                    await session.execute(
                        select(SotkaEvent)
                        .where(SotkaEvent.available_on >= start, SotkaEvent.available_on <= end)
                        .order_by(SotkaEvent.starts_at, SotkaEvent.available_on, SotkaEvent.subject)
                    )
                ).scalars()
            )

    async def mark_block(self, block_id: int, status: BlockStatus) -> None:
        ratio = {
            BlockStatus.DONE: 1.0,
            BlockStatus.PARTIAL: 0.5,
            BlockStatus.SKIPPED: 0.0,
            BlockStatus.MOVED: 0.0,
            BlockStatus.PLANNED: 0.0,
        }[status]
        async with self.database.sessions() as session:
            block = await session.get(PlanBlock, block_id)
            if block is None:
                raise ValueError("plan block not found")
            block.status = status
            block.completion_ratio = ratio
            await session.commit()

    async def update_preference(self, user_id: int, field: str, value: object) -> None:
        allowed = {
            "wake_time",
            "bedtime",
            "leave_0800",
            "leave_0850",
            "travel_home_minutes",
            "rest_minutes",
            "focus_minutes",
            "break_minutes",
            "reminder_minutes",
        }
        if field not in allowed:
            raise ValueError("unsupported preference")
        async with self.database.sessions() as session:
            preferences = await session.get(UserPreferences, user_id)
            if preferences is None:
                raise ValueError("user preferences not found")
            setattr(preferences, field, value)
            await session.commit()
