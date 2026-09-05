from datetime import UTC, datetime, timedelta

from time_manager.sotka import parse_calendar_payload, token_expiration


def test_calendar_filters_courses_and_combines_blocks() -> None:
    payload = {
        "data": [
            {
                "theoriesAndPractices": [
                    {
                        "practic": {
                            "course_name": "Профильная математика с Александром | ЕГЭ 2027",
                            "course_id": 10,
                            "lesson_id": 101,
                            "start_at": "2026-09-02T12:30:00.000000Z",
                            "lesson_duration": "02:00:00",
                        }
                    },
                    {
                        "practic": {
                            "course_name": "Профильная математика с Александром | ЕГЭ 2027",
                            "course_id": 10,
                            "lesson_id": 102,
                            "start_at": "2026-09-02T15:00:00.000000Z",
                            "lesson_duration": "02:00:00",
                        }
                    },
                    {
                        "practic": {
                            "course_name": "Блок 1. Вайбкодинг",
                            "start_at": "2026-09-02T10:00:00.000000Z",
                        }
                    },
                ]
            }
        ]
    }
    result = parse_calendar_payload(payload)
    assert len(result) == 2
    assert all(item.subject == "Математика" for item in result)
    assert sum(item.duration_minutes for item in result) == 300
    assert result[0].lesson_url == "https://old-platform.sotkaonline.ru/courses/10/101"


def test_unselected_social_studies_teacher_is_ignored() -> None:
    payload = {
        "data": [
            {
                "theoriesAndPractices": [
                    {
                        "practic": {
                            "course_name": "Обществознание с Алексеем | ЕГЭ 2027",
                            "course_id": 20,
                            "lesson_id": 201,
                            "start_at": "2026-09-05T12:30:00Z",
                        }
                    },
                    {
                        "practic": {
                            "course_name": "Обществознание с Ксенией | ЕГЭ 2027",
                            "course_id": 21,
                            "lesson_id": 202,
                            "start_at": "2026-09-05T12:30:00Z",
                            "lesson_duration": "02:00:00",
                        }
                    },
                ]
            }
        ]
    }
    result = parse_calendar_payload(payload)
    assert [(x.subject, x.duration_minutes) for x in result] == [("Обществознание", 150)]

    ksenia_only = {
        "data": [
            {
                "theoriesAndPractices": [
                    {
                        "practic": {
                            "course_name": "Обществознание с Ксенией | ЕГЭ 2027",
                            "course_id": 21,
                            "lesson_id": 203,
                            "start_at": "2026-09-06T12:30:00Z",
                        }
                    }
                ]
            }
        ]
    }
    assert parse_calendar_payload(ksenia_only) == []


def test_token_expiration_reads_jwt_without_verifying_secret() -> None:
    import base64
    import json

    expires = datetime.now(UTC) + timedelta(days=365)
    payload = base64.urlsafe_b64encode(json.dumps({"exp": expires.timestamp()}).encode()).decode()
    result = token_expiration(f"header.{payload.rstrip('=')}.signature")
    assert result is not None
    assert result.date() == expires.date()
