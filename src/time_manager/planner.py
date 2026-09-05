from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .importers import SchoolEvent
from .models import BlockKind


@dataclass(frozen=True)
class PlannerSettings:
    wake_time: time = time(5, 45)
    bedtime: time = time(21, 45)
    leave_0800: time = time(7, 0)
    leave_0850: time = time(7, 50)
    travel_home_minutes: int = 45
    breakfast_minutes: int = 20
    lunch_minutes: int = 30
    dinner_minutes: int = 30
    rest_minutes: int = 45
    focus_minutes: int = 50
    break_minutes: int = 10


@dataclass(frozen=True)
class Workload:
    kind: BlockKind
    title: str
    minutes: int
    source_event_id: int | None = None


@dataclass(frozen=True)
class PlannedBlock:
    start: datetime
    end: datetime
    kind: BlockKind
    title: str
    source_event_id: int | None = None


@dataclass(frozen=True)
class PlanResult:
    blocks: tuple[PlannedBlock, ...]
    unscheduled: tuple[Workload, ...]

    @property
    def unscheduled_minutes(self) -> int:
        return sum(item.minutes for item in self.unscheduled)


def _at(day: date, value: time, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, value, tzinfo=tz)


def _add(
    blocks: list[PlannedBlock], start: datetime, minutes: int, kind: BlockKind, title: str
) -> datetime:
    end = start + timedelta(minutes=minutes)
    blocks.append(PlannedBlock(start, end, kind, title))
    return end


def _free_windows(
    start: datetime, end: datetime, occupied: list[PlannedBlock]
) -> list[tuple[datetime, datetime]]:
    windows: list[tuple[datetime, datetime]] = []
    cursor = start
    for block in sorted(occupied, key=lambda item: item.start):
        if block.end <= cursor or block.start >= end:
            continue
        if block.start > cursor:
            windows.append((cursor, min(block.start, end)))
        cursor = max(cursor, block.end)
    if cursor < end:
        windows.append((cursor, end))
    return windows


def build_day_plan(
    day: date,
    school: list[SchoolEvent],
    homework_minutes: int,
    sotka: list[Workload],
    settings: PlannerSettings,
    tz: ZoneInfo,
) -> PlanResult:
    blocks: list[PlannedBlock] = []
    wake = _at(day, settings.wake_time, tz)
    bedtime = _at(day, settings.bedtime, tz)
    lessons = sorted(
        (item for item in school if item.weekday == day.weekday()), key=lambda x: x.start
    )

    if lessons:
        first_start = _at(day, lessons[0].start, tz)
        leave = _at(
            day, settings.leave_0800 if lessons[0].start == time(8) else settings.leave_0850, tz
        )
        _add(blocks, wake, settings.breakfast_minutes, BlockKind.MEAL, "Завтрак")
        blocks.append(PlannedBlock(leave, first_start, BlockKind.TRAVEL, "Дорога в школу"))
        for lesson in lessons:
            blocks.append(
                PlannedBlock(
                    _at(day, lesson.start, tz),
                    _at(day, lesson.end, tz),
                    BlockKind.SCHOOL,
                    lesson.subject,
                )
            )
        arrival = _at(day, lessons[-1].end, tz)
        arrival = _add(
            blocks, arrival, settings.travel_home_minutes, BlockKind.TRAVEL, "Дорога домой"
        )
        after_lunch = _add(blocks, arrival, settings.lunch_minutes, BlockKind.MEAL, "Обед")
        study_start = _add(blocks, after_lunch, settings.rest_minutes, BlockKind.REST, "Отдых")
    else:
        _add(blocks, wake, settings.breakfast_minutes, BlockKind.MEAL, "Завтрак")
        study_start = _at(day, time(10), tz)
        _add(blocks, _at(day, time(13), tz), settings.lunch_minutes, BlockKind.MEAL, "Обед")

    dinner_start = _at(day, time(19), tz)
    if dinner_start < study_start:
        dinner_start = study_start
    if dinner_start + timedelta(minutes=settings.dinner_minutes) <= bedtime:
        _add(blocks, dinner_start, settings.dinner_minutes, BlockKind.MEAL, "Ужин")

    pending: list[Workload] = []
    if homework_minutes > 0:
        pending.append(Workload(BlockKind.HOMEWORK, "Школьное ДЗ", homework_minutes))
    pending.extend(item for item in sotka if item.minutes > 0)

    unscheduled: list[Workload] = []
    cursor = study_start
    for workload in pending:
        remaining = workload.minutes
        while remaining > 0:
            windows = _free_windows(cursor, bedtime, blocks)
            suitable = next(
                (
                    window
                    for window in windows
                    if (window[1] - window[0]).total_seconds() >= min(remaining, 25) * 60
                ),
                None,
            )
            if suitable is None:
                break
            block_start, window_end = suitable
            capacity = int((window_end - block_start).total_seconds() // 60)
            duration = min(remaining, settings.focus_minutes, capacity)
            if duration < 25 and remaining > duration:
                cursor = window_end
                continue
            block_end = block_start + timedelta(minutes=duration)
            blocks.append(
                PlannedBlock(
                    block_start,
                    block_end,
                    workload.kind,
                    workload.title,
                    workload.source_event_id,
                )
            )
            remaining -= duration
            cursor = block_end + timedelta(minutes=settings.break_minutes)
        if remaining:
            unscheduled.append(
                Workload(workload.kind, workload.title, remaining, workload.source_event_id)
            )
    return PlanResult(tuple(sorted(blocks, key=lambda item: item.start)), tuple(unscheduled))
