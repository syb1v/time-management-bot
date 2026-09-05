from datetime import UTC, date, datetime, timedelta

from time_manager.db import Database
from time_manager.models import BlockKind, BlockStatus, PlanBlock
from time_manager.stats import build_stats, render_chart


async def test_stats_aggregate_and_render_png() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.initialize(1, 2)
    start = datetime(2026, 9, 3, 15, tzinfo=UTC)
    async with database.sessions() as session:
        session.add(
            PlanBlock(
                user_id=1,
                day=date(2026, 9, 3),
                start_at=start,
                end_at=start + timedelta(minutes=60),
                kind=BlockKind.HOMEWORK,
                title="ДЗ",
                status=BlockStatus.PARTIAL,
                completion_ratio=0.5,
            )
        )
        await session.commit()
    summary = await build_stats(database, 1, date(2026, 9, 3), 7)
    assert summary.planned_minutes == 60
    assert summary.completed_minutes == 30
    assert summary.homework_minutes == 60
    assert render_chart(summary).startswith(b"\x89PNG")
    await database.close()
