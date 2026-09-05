from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import event, inspect, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .models import Base, Role, User, UserPreferences


class Database:
    def __init__(self, url: str) -> None:
        if url.startswith("sqlite") and "///" in url:
            database_path = url.split("///", 1)[1]
            if database_path != ":memory:":
                Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self.engine: AsyncEngine = create_async_engine(url)
        if url.startswith("sqlite"):
            event.listen(self.engine.sync_engine, "connect", self._configure_sqlite)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    @staticmethod
    def _configure_sqlite(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async def initialize(self, student_id: int, owner_id: int) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.run_sync(self._upgrade_schema)
        async with self.sessions() as session:
            for telegram_id, role in ((student_id, Role.STUDENT), (owner_id, Role.OWNER)):
                if await session.get(User, telegram_id) is None:
                    session.add(
                        User(
                            telegram_id=telegram_id,
                            role=role,
                            created_at=datetime.now(UTC),
                            preferences=UserPreferences(),
                        )
                    )
            await session.commit()

    @staticmethod
    def _upgrade_schema(connection: Connection) -> None:
        inspector = inspect(connection)
        if inspector is None:
            raise RuntimeError("SQLAlchemy inspector is unavailable")
        columns = {item["name"] for item in inspector.get_columns("sotka_events")}
        additions = {
            "course_name": "VARCHAR(180)",
            "course_id": "INTEGER",
            "lesson_id": "INTEGER",
            "starts_at": "DATETIME",
            "lesson_url": "TEXT",
            "viewed": "BOOLEAN NOT NULL DEFAULT 0",
            "homework_done": "BOOLEAN NOT NULL DEFAULT 0",
        }
        for name, sql_type in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE sotka_events ADD COLUMN {name} {sql_type}"))

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessions() as session:
            yield session

    async def preferences(self, user_id: int) -> UserPreferences:
        async with self.sessions() as session:
            result = await session.execute(
                select(UserPreferences).where(UserPreferences.user_id == user_id)
            )
            return result.scalar_one()

    async def close(self) -> None:
        await self.engine.dispose()
