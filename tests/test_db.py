from datetime import UTC, datetime

from time_manager.db import Database
from time_manager.models import BlockKind, PlanBlock, Role


async def test_database_creates_allowlisted_users() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.initialize(1359806027, 6499614618)
    preferences = await database.preferences(1359806027)
    assert preferences.wake_time.hour == 5
    async with database.sessions() as session:
        user = await session.get(
            __import__("time_manager.models", fromlist=["User"]).User, 6499614618
        )
        assert user is not None and user.role == Role.OWNER
    await database.close()


async def test_database_round_trips_aware_utc_datetimes() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.initialize(1, 2)
    start = datetime(2026, 9, 3, 12, tzinfo=UTC)
    async with database.sessions() as session:
        block = PlanBlock(
            user_id=1,
            day=start.date(),
            start_at=start,
            end_at=start.replace(hour=13),
            kind=BlockKind.HOMEWORK,
            title="ДЗ",
        )
        session.add(block)
        await session.commit()
        await session.refresh(block)
        assert block.start_at == start
        assert block.start_at.tzinfo is UTC
    await database.close()
