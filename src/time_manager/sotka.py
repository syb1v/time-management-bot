from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import aiohttp

from .importers import SotkaEventData

COURSES = frozenset(
    {
        "Русский язык с Дашей | ЕГЭ 2027",
        "Обществознание с Алексеем | ЕГЭ 2027",
        "Профильная математика с Александром | ЕГЭ 2027",
    }
)

SUBJECTS = {
    "Русский язык с Дашей | ЕГЭ 2027": "Русский язык",
    "Обществознание с Алексеем | ЕГЭ 2027": "Обществознание",
    "Профильная математика с Александром | ЕГЭ 2027": "Математика",
}


class SotkaAPIError(RuntimeError):
    pass


def token_expiration(token: str) -> datetime | None:
    import base64
    import json

    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return datetime.fromtimestamp(float(data["exp"]), UTC)
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _duration_minutes(value: object) -> int:
    if not isinstance(value, str):
        return 150
    try:
        hours, minutes, seconds = (int(part) for part in value.split(":"))
    except (ValueError, TypeError):
        return 150
    api_minutes = hours * 60 + minutes + round(seconds / 60)
    # The platform duration excludes practice/break time; reserve the agreed 2.5h minimum.
    return max(150, api_minutes)


def parse_calendar_payload(payload: Mapping[str, Any]) -> list[SotkaEventData]:
    result: dict[str, SotkaEventData] = {}
    data = payload.get("data")
    if not isinstance(data, list):
        raise SotkaAPIError("calendar response has no data array")
    for block in data:
        if not isinstance(block, Mapping):
            continue
        entries = block.get("theoriesAndPractices")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            lesson = entry.get("practic")
            if not isinstance(lesson, Mapping):
                continue
            course = lesson.get("course_name")
            start_at = lesson.get("start_at")
            if course not in COURSES or not isinstance(start_at, str):
                continue
            try:
                starts_at = datetime.fromisoformat(start_at.replace("Z", "+00:00")).astimezone(UTC)
                course_id = int(lesson["course_id"])
                lesson_id = int(lesson["lesson_id"])
            except (KeyError, TypeError, ValueError):
                continue
            key = f"api:{course_id}:{lesson_id}"
            result[key] = SotkaEventData(
                subject=SUBJECTS[str(course)],
                available_on=starts_at.date(),
                duration_minutes=_duration_minutes(lesson.get("lesson_duration")),
                external_key=key,
                course_name=str(course),
                course_id=course_id,
                lesson_id=lesson_id,
                starts_at=starts_at,
                lesson_url=(f"https://old-platform.sotkaonline.ru/courses/{course_id}/{lesson_id}"),
                viewed=bool(lesson.get("performed")),
                homework_done=bool(lesson.get("standart_homework_performed")),
            )
    return sorted(
        result.values(), key=lambda item: (item.available_on, item.subject, item.lesson_id or 0)
    )


@dataclass(frozen=True)
class SotkaClient:
    token: str
    base_url: str = "https://admin.sotkaonline.ru/api/v1"

    async def calendar(self, date_from: date, date_to: date) -> list[SotkaEventData]:
        expiration = token_expiration(self.token)
        if expiration is not None and expiration <= datetime.now(UTC) + timedelta(days=7):
            raise SotkaAPIError("Sotka token is expired or expires within 7 days")
        events: dict[str, SotkaEventData] = {}
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            cursor = date_from
            while cursor <= date_to:
                window_end = min(cursor + timedelta(days=6), date_to)
                params = {
                    "date_from": cursor.strftime("%d.%m.%Y"),
                    "date_to": window_end.strftime("%d.%m.%Y"),
                    "favorite": "0",
                }
                try:
                    async with session.get(f"{self.base_url}/calendar", params=params) as response:
                        if response.status in (401, 403):
                            raise SotkaAPIError("Sotka rejected the API token")
                        if response.status != 200:
                            raise SotkaAPIError(f"Sotka calendar returned HTTP {response.status}")
                        payload = await response.json()
                except (aiohttp.ClientError, TimeoutError) as error:
                    raise SotkaAPIError(f"Sotka request failed: {type(error).__name__}") from error
                for event in parse_calendar_payload(payload):
                    if not date_from <= event.available_on <= date_to:
                        continue
                    if event.external_key is not None:
                        events[event.external_key] = event
                cursor = window_end + timedelta(days=1)
        return sorted(events.values(), key=lambda item: (item.available_on, item.subject))
