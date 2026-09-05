from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .bot import create_dispatcher
from .config import get_settings
from .db import Database
from .jobs import send_due_reminders, synchronize_sotka
from .services import PlanningService
from .sotka import SotkaAPIError, SotkaClient


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = get_settings()
    database = Database(settings.database_url)
    await database.initialize(settings.student_id, settings.owner_id)
    service = PlanningService(database, settings.tz)
    await service.import_school(settings.school_schedule_path)
    # Markdown is only a first-run seed. A failed API call retains the last API cache.
    if not await service.has_sotka_events():
        await service.import_files(
            settings.school_schedule_path,
            settings.sotka_schedule_path,
            datetime.now(settings.tz).year,
        )
    if settings.sotka_api_token:
        try:
            today = datetime.now(settings.tz).date()
            events = await SotkaClient(settings.sotka_api_token).calendar(
                today.replace(day=1), today + timedelta(days=settings.sotka_sync_days)
            )
            await service.import_sotka_events(events)
            await service.regenerate_range(settings.student_id, today, 7)
        except SotkaAPIError:
            logging.exception("Sotka API synchronization failed; retaining cached events")
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = create_dispatcher(settings, service)
    scheduler = AsyncIOScheduler(timezone=settings.tz)
    scheduler.add_job(
        send_due_reminders,
        "interval",
        minutes=1,
        kwargs={
            "bot": bot,
            "database": database,
            "student_id": settings.student_id,
            "timezone": settings.tz,
        },
        max_instances=1,
        coalesce=True,
    )
    if settings.sotka_api_token:
        scheduler.add_job(
            synchronize_sotka,
            "cron",
            hour=3,
            minute=15,
            kwargs={
                "bot": bot,
                "service": service,
                "owner_id": settings.owner_id,
                "student_id": settings.student_id,
                "token": settings.sotka_api_token,
                "sync_days": settings.sotka_sync_days,
            },
            max_instances=1,
            coalesce=True,
        )
    scheduler.start()
    try:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
