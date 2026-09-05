from __future__ import annotations

from datetime import UTC, datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from .db import Database
from .models import PlanBlock, UserPreferences
from .panel import show_text
from .services import PlanningService
from .sotka import SotkaAPIError, SotkaClient


async def send_due_reminders(
    bot: Bot, database: Database, student_id: int, timezone: ZoneInfo
) -> None:
    now = datetime.now(UTC)
    async with database.sessions() as session:
        preferences = await session.get(UserPreferences, student_id)
        if preferences is None or not preferences.notifications_enabled:
            return
        until = now + timedelta(minutes=preferences.reminder_minutes)
        blocks = list(
            (
                await session.execute(
                    select(PlanBlock).where(
                        PlanBlock.user_id == student_id,
                        PlanBlock.start_at >= now,
                        PlanBlock.start_at <= until,
                        PlanBlock.reminder_sent.is_(False),
                    )
                )
            ).scalars()
        )
        for block in blocks:
            start = block.start_at.astimezone(timezone)
            end = block.end_at.astimezone(timezone)
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="Готово", callback_data=f"done:{block.id}"),
                        InlineKeyboardButton(text="50%", callback_data=f"partial:{block.id}"),
                        InlineKeyboardButton(text="Перенести", callback_data=f"move:{block.id}"),
                        InlineKeyboardButton(text="Пропустить", callback_data=f"skip:{block.id}"),
                    ]
                ]
            )
            await show_text(
                bot,
                database,
                student_id,
                f"<b>Скоро начнётся</b>\n\n{escape(block.title)}\n"
                f"<code>{start:%H:%M}–{end:%H:%M}</code>",
                keyboard,
            )
            block.reminder_sent = True
        await session.commit()


async def synchronize_sotka(
    bot: Bot,
    service: PlanningService,
    owner_id: int,
    student_id: int,
    token: str,
    sync_days: int,
) -> None:
    today = datetime.now(service.timezone).date()
    try:
        events = await SotkaClient(token).calendar(
            today.replace(day=1), today + timedelta(days=sync_days)
        )
        await service.import_sotka_events(events)
        await service.regenerate_range(student_id, today, 7)
    except (SotkaAPIError, ValueError) as error:
        await bot.send_message(
            owner_id,
            "<b>Синхронизация Сотки не удалась.</b>\n"
            f"{type(error).__name__}: {error}\n"
            "Старый кэш сохранён. Проверь <code>SOTKA_API_TOKEN</code>.",
        )
