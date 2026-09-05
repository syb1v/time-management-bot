from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Dispatcher
from aiogram.types import CallbackQuery, Message, TelegramObject

from .config import Settings
from .handlers import router
from .services import PlanningService


class AccessMiddleware(BaseMiddleware):
    def __init__(self, allowed_ids: frozenset[int]) -> None:
        self.allowed_ids = allowed_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None or user.id not in self.allowed_ids:
            if isinstance(event, CallbackQuery):
                await event.answer("Нет доступа", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("Этот бот приватный.")
            return None
        return await handler(event, data)


def create_dispatcher(settings: Settings, service: PlanningService) -> Dispatcher:
    dispatcher = Dispatcher()
    middleware = AccessMiddleware(settings.allowed_ids)
    dispatcher.message.outer_middleware(middleware)
    dispatcher.callback_query.outer_middleware(middleware)
    dispatcher["settings"] = settings
    dispatcher["service"] = service
    dispatcher.include_router(router)
    return dispatcher
