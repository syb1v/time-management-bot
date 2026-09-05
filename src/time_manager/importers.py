from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True)
class SchoolEvent:
    weekday: int
    start: time
    end: time
    subject: str
    details: str = ""


@dataclass(frozen=True)
class SotkaEventData:
    subject: str
    available_on: date
    duration_minutes: int
    external_key: str | None = None
    course_name: str | None = None
    course_id: int | None = None
    lesson_id: int | None = None
    starts_at: datetime | None = None
    lesson_url: str | None = None
    viewed: bool = False
    homework_done: bool = False


_DAYS = {"Понедельник": 0, "Вторник": 1, "Среда": 2, "Четверг": 3, "Пятница": 4}
_DATE_RE = re.compile(r"- (\d+) сентября — ≈ ([\d,]+) ч")


def _parse_time(value: str) -> time:
    hour, minute = (int(part) for part in value.split(":"))
    return time(hour, minute)


def parse_school_schedule(text: str) -> list[SchoolEvent]:
    events: list[SchoolEvent] = []
    current_day: int | None = None
    for raw in text.splitlines():
        heading = re.match(r"### (.+)", raw)
        if heading:
            current_day = _DAYS.get(heading.group(1).strip())
            continue
        if current_day is None or not raw.startswith("- **"):
            continue
        match = re.match(r"- \*\*(\d{2}:\d{2})–(\d{2}:\d{2}) — ([^*]+)\*\*(?: — (.*))?", raw)
        if not match:
            continue
        events.append(
            SchoolEvent(
                current_day,
                _parse_time(match.group(1)),
                _parse_time(match.group(2)),
                match.group(3).strip().rstrip(":"),
                (match.group(4) or "").strip(),
            )
        )
    if not events:
        raise ValueError("school schedule contains no day-list events")
    return events


def parse_sotka_schedule(text: str, year: int) -> list[SotkaEventData]:
    subject: str | None = None
    events: list[SotkaEventData] = []
    for raw in text.splitlines():
        heading = re.match(r"## (.+)", raw)
        if heading:
            subject = heading.group(1).strip()
            continue
        match = _DATE_RE.match(raw.strip())
        if subject and match:
            hours = float(match.group(2).replace(",", "."))
            events.append(
                SotkaEventData(subject, date(year, 9, int(match.group(1))), round(hours * 60))
            )
    if not events:
        raise ValueError("Sotka schedule contains no events")
    return events


def next_subject_deadlines(events: list[SotkaEventData]) -> dict[int, date]:
    by_subject: dict[str, list[date]] = {}
    for event in events:
        by_subject.setdefault(event.subject, []).append(event.available_on)
    result: dict[int, date] = {}
    for event in events:
        later = sorted(d for d in by_subject[event.subject] if d > event.available_on)
        result[id(event)] = (
            later[0] - timedelta(days=1) if later else event.available_on + timedelta(days=7)
        )
    return result
