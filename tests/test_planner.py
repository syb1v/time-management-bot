from datetime import date, time
from zoneinfo import ZoneInfo

from time_manager.importers import SchoolEvent
from time_manager.models import BlockKind
from time_manager.planner import PlannerSettings, Workload, build_day_plan

TZ = ZoneInfo("Europe/Moscow")


def test_plan_protects_bedtime_and_splits_work() -> None:
    monday = date(2026, 9, 7)
    school = [SchoolEvent(0, time(8, 50), time(15, 5), "Школа")]
    result = build_day_plan(
        monday,
        school,
        120,
        [Workload(BlockKind.SOTKA, "Математика", 300, 1)],
        PlannerSettings(),
        TZ,
    )
    assert max(block.end.time() for block in result.blocks) <= time(21, 45)
    study = [b for b in result.blocks if b.kind in (BlockKind.HOMEWORK, BlockKind.SOTKA)]
    assert all((b.end - b.start).total_seconds() <= 50 * 60 for b in study)
    assert result.unscheduled_minutes > 0


def test_plan_uses_separate_late_start_departure() -> None:
    monday = date(2026, 9, 7)
    result = build_day_plan(
        monday,
        [SchoolEvent(0, time(8, 50), time(9, 30), "Экология")],
        0,
        [],
        PlannerSettings(leave_0850=time(7, 40)),
        TZ,
    )
    travel = next(block for block in result.blocks if block.title == "Дорога в школу")
    assert travel.start.time() == time(7, 40)


def test_thursday_extra_lesson_delays_arrival() -> None:
    thursday = date(2026, 9, 3)
    school = [
        SchoolEvent(3, time(8), time(14, 10), "Школа"),
        SchoolEvent(3, time(15, 15), time(16, 35), "Допы по математике"),
    ]
    result = build_day_plan(thursday, school, 60, [], PlannerSettings(), TZ)
    homework = next(block for block in result.blocks if block.kind == BlockKind.HOMEWORK)
    assert homework.start.time() >= time(17, 50)
