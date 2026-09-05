from __future__ import annotations

from contextlib import suppress

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, Message

from .db import Database
from .models import Dashboard


async def safe_delete(bot: Bot, chat_id: int, message_id: int) -> None:
    with suppress(TelegramBadRequest):
        await bot.delete_message(chat_id, message_id)


async def _dashboard(database: Database, chat_id: int) -> Dashboard | None:
    async with database.sessions() as session:
        return await session.get(Dashboard, chat_id)


async def _save(database: Database, chat_id: int, message_id: int, media_type: str) -> None:
    async with database.sessions() as session:
        dashboard = await session.get(Dashboard, chat_id)
        if dashboard is None:
            session.add(Dashboard(chat_id=chat_id, message_id=message_id, media_type=media_type))
        else:
            dashboard.message_id = message_id
            dashboard.media_type = media_type
        await session.commit()


async def show_text(
    bot: Bot,
    database: Database,
    chat_id: int,
    text: str,
    keyboard: InlineKeyboardMarkup,
) -> Message | None:
    dashboard = await _dashboard(database, chat_id)
    if dashboard is not None and dashboard.media_type == "text":
        try:
            result = await bot.edit_message_text(
                text, chat_id=chat_id, message_id=dashboard.message_id, reply_markup=keyboard
            )
            return result if isinstance(result, Message) else None
        except TelegramBadRequest as error:
            if "message is not modified" in str(error):
                return None
            if "message to edit not found" not in str(error):
                raise
    if dashboard is not None:
        await safe_delete(bot, chat_id, dashboard.message_id)
    message = await bot.send_message(chat_id, text, reply_markup=keyboard)
    await _save(database, chat_id, message.message_id, "text")
    return message


async def show_photo(
    bot: Bot,
    database: Database,
    chat_id: int,
    image: bytes,
    caption: str,
    keyboard: InlineKeyboardMarkup,
) -> Message:
    dashboard = await _dashboard(database, chat_id)
    if dashboard is not None:
        await safe_delete(bot, chat_id, dashboard.message_id)
    message = await bot.send_photo(
        chat_id,
        BufferedInputFile(image, filename="statistics.png"),
        caption=caption,
        reply_markup=keyboard,
    )
    await _save(database, chat_id, message.message_id, "photo")
    return message
