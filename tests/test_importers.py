from datetime import date

from time_manager.importers import parse_school_schedule, parse_sotka_schedule


def test_school_imports_day_list_without_table_duplicates() -> None:
    text = "### Понедельник\n- **08:50–09:30 — Экология** — Носенко Е. П., каб. 161."
    result = parse_school_schedule(text)
    assert len(result) == 1
    assert result[0].subject == "Экология"
    assert result[0].start.hour == 8


def test_sotka_imports_decimal_hours() -> None:
    text = "## Математика\n- 2 сентября — ≈ 2,5 ч"
    result = parse_sotka_schedule(text, 2026)
    assert result == [result[0]]
    assert result[0].available_on == date(2026, 9, 2)
    assert result[0].duration_minutes == 150
