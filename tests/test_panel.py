from datetime import UTC, datetime
from unittest.mock import AsyncMock

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageText
from aiogram.types import Chat, Message

from time_manager.db import Database
from time_manager.keyboards import home_keyboard
from time_manager.models import Dashboard
from time_manager.panel import show_text


def _message(message_id: int, text: str = "Панель") -> Message:
    return Message(
        message_id=message_id,
        date=datetime.now(UTC),
        chat=Chat(id=1, type="private"),
        text=text,
    )


async def test_show_text_creates_and_persists_dashboard() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.initialize(1, 2)
    bot = AsyncMock()
    bot.send_message.return_value = _message(42)
    await show_text(bot, database, 1, "Панель", home_keyboard())
    async with database.sessions() as session:
        dashboard = await session.get(Dashboard, 1)
        assert dashboard is not None
        assert dashboard.message_id == 42
    await database.close()


async def test_unchanged_dashboard_is_accepted() -> None:
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.initialize(1, 2)
    async with database.sessions() as session:
        session.add(Dashboard(chat_id=1, message_id=42, media_type="text"))
        await session.commit()
    method = EditMessageText(chat_id=1, message_id=42, text="Панель")
    bot = AsyncMock()
    bot.edit_message_text.side_effect = TelegramBadRequest(method, "message is not modified")
    await show_text(bot, database, 1, "Панель", home_keyboard())
    bot.send_message.assert_not_awaited()
    await database.close()
