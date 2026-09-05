from __future__ import annotations

from datetime import datetime, time, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .config import Settings
from .keyboards import (
    blocks_keyboard,
    cancel_keyboard,
    home_keyboard,
    settings_keyboard,
    sotka_keyboard,
    stats_keyboard,
)
from .models import BlockStatus
from .panel import safe_delete, show_photo, show_text
from .render import render_day, render_settings, render_sotka, render_week
from .services import PlanningService
from .sotka import SotkaAPIError, SotkaClient
from .stats import build_stats, render_chart, render_stats

router = Router(name="main")


class InputState(StatesGroup):
    homework = State()
    sleep = State()
    setting = State()


def _callback_chat_id(callback: CallbackQuery) -> int:
    if not isinstance(callback.message, Message):
        raise ValueError("callback has no accessible chat message")
    return callback.message.chat.id


def _callback_data(callback: CallbackQuery) -> str:
    if callback.data is None:
        raise ValueError("callback has no data")
    return callback.data


async def _today_panel(
    bot: Bot, chat_id: int, settings: Settings, service: PlanningService, owner: bool
) -> None:
    day = datetime.now(settings.tz).date()
    await service.regenerate_day(settings.student_id, day)
    blocks = await service.blocks(settings.student_id, day)
    await show_text(
        bot,
        service.database,
        chat_id,
        render_day(day, blocks, settings.tz),
        home_keyboard(owner),
    )


@router.message(CommandStart())
@router.message(Command("menu"))
async def start(message: Message, bot: Bot, settings: Settings, service: PlanningService) -> None:
    await safe_delete(bot, message.chat.id, message.message_id)
    await service.ensure_week(settings.student_id, datetime.now(settings.tz).date())
    await _today_panel(
        bot,
        message.chat.id,
        settings,
        service,
        message.from_user is not None and message.from_user.id == settings.owner_id,
    )


@router.callback_query(F.data == "view:today")
async def today(
    callback: CallbackQuery, bot: Bot, settings: Settings, service: PlanningService
) -> None:
    await _today_panel(
        bot,
        _callback_chat_id(callback),
        settings,
        service,
        callback.from_user.id == settings.owner_id,
    )
    await callback.answer()


@router.callback_query(F.data == "view:week")
async def week(
    callback: CallbackQuery, bot: Bot, settings: Settings, service: PlanningService
) -> None:
    start_day = datetime.now(settings.tz).date()
    await service.ensure_week(settings.student_id, start_day)
    days = [
        (
            start_day + timedelta(days=i),
            await service.blocks(settings.student_id, start_day + timedelta(days=i)),
        )
        for i in range(7)
    ]
    await show_text(
        bot,
        service.database,
        _callback_chat_id(callback),
        render_week(days),
        home_keyboard(callback.from_user.id == settings.owner_id),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^stats:(7|30|183|365)$"))
@router.callback_query(F.data == "view:stats")
async def statistics(
    callback: CallbackQuery, bot: Bot, settings: Settings, service: PlanningService
) -> None:
    days = (
        int(_callback_data(callback).split(":", 1)[1])
        if _callback_data(callback).startswith("stats:")
        else 7
    )
    summary = await build_stats(
        service.database, settings.student_id, datetime.now(settings.tz).date(), days
    )
    await show_photo(
        bot,
        service.database,
        _callback_chat_id(callback),
        render_chart(summary),
        render_stats(summary),
        stats_keyboard(days),
    )
    await callback.answer()


@router.callback_query(F.data == "view:sotka")
async def sotka_panel(
    callback: CallbackQuery, bot: Bot, settings: Settings, service: PlanningService
) -> None:
    day = datetime.now(settings.tz).date()
    events = await service.sotka_events(day - timedelta(days=7), day + timedelta(days=30))
    await show_text(
        bot,
        service.database,
        _callback_chat_id(callback),
        render_sotka(events, settings.tz, day),
        sotka_keyboard(events, callback.from_user.id == settings.owner_id),
    )
    await callback.answer()


@router.callback_query(F.data == "view:checkin")
async def checkin(
    callback: CallbackQuery, bot: Bot, settings: Settings, service: PlanningService
) -> None:
    if callback.from_user.id != settings.student_id:
        await callback.answer("Отмечаться может только ученица", show_alert=True)
        return
    blocks = await service.blocks(settings.student_id, datetime.now(settings.tz).date())
    await show_text(
        bot,
        service.database,
        _callback_chat_id(callback),
        "<b>Отметка выполнения</b>\n\nВыбери результат для учебного блока.",
        blocks_keyboard(blocks),
    )
    await callback.answer()


@router.callback_query(F.data == "input:homework")
async def ask_homework(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    service: PlanningService,
) -> None:
    if callback.from_user.id != settings.student_id:
        await callback.answer("Изменять нагрузку может только ученица", show_alert=True)
        return
    await state.set_state(InputState.homework)
    await show_text(
        bot,
        service.database,
        _callback_chat_id(callback),
        "<b>Школьное ДЗ</b>\n\nПришли количество часов одним сообщением.\n"
        "Например: <code>2.5</code>",
        cancel_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "input:sleep")
async def ask_sleep(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    service: PlanningService,
) -> None:
    if callback.from_user.id != settings.student_id:
        await callback.answer("Отмечать сон может только ученица", show_alert=True)
        return
    await state.set_state(InputState.sleep)
    await show_text(
        bot,
        service.database,
        _callback_chat_id(callback),
        "<b>Сон</b>\n\nСколько часов удалось поспать?\nНапример: <code>7.5</code>",
        cancel_keyboard(),
    )
    await callback.answer()


@router.message(InputState.homework)
async def save_homework(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    service: PlanningService,
) -> None:
    await safe_delete(bot, message.chat.id, message.message_id)
    try:
        hours = float((message.text or "").replace(",", "."))
        await service.set_homework(
            settings.student_id, datetime.now(settings.tz).date(), round(hours * 60)
        )
    except ValueError:
        await show_text(
            bot,
            service.database,
            message.chat.id,
            "<b>Некорректное значение</b>\n\nВведи число от 0 до 12. Например: <code>2.5</code>",
            cancel_keyboard(),
        )
        return
    await state.clear()
    await _today_panel(bot, message.chat.id, settings, service, False)


@router.message(InputState.sleep)
async def save_sleep(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    service: PlanningService,
) -> None:
    await safe_delete(bot, message.chat.id, message.message_id)
    try:
        hours = float((message.text or "").replace(",", "."))
        await service.set_sleep(settings.student_id, datetime.now(settings.tz).date(), hours)
    except ValueError:
        await show_text(
            bot,
            service.database,
            message.chat.id,
            "<b>Некорректное значение</b>\n\nВведи число от 0 до 16. Например: <code>7.5</code>",
            cancel_keyboard(),
        )
        return
    await state.clear()
    await _today_panel(bot, message.chat.id, settings, service, False)


@router.callback_query(F.data.regexp(r"^(done|partial|move|skip):\d+$"))
async def mark(
    callback: CallbackQuery, bot: Bot, settings: Settings, service: PlanningService
) -> None:
    if callback.from_user.id != settings.student_id:
        await callback.answer("Отмечаться может только ученица", show_alert=True)
        return
    action, raw_id = _callback_data(callback).split(":", 1)
    status = {
        "done": BlockStatus.DONE,
        "partial": BlockStatus.PARTIAL,
        "move": BlockStatus.MOVED,
        "skip": BlockStatus.SKIPPED,
    }[action]
    await service.mark_block(int(raw_id), status)
    blocks = await service.blocks(settings.student_id, datetime.now(settings.tz).date())
    await show_text(
        bot,
        service.database,
        _callback_chat_id(callback),
        "<b>Отметка выполнения</b>\n\nРезультат сохранён. Можно отметить следующий блок.",
        blocks_keyboard(blocks),
    )
    await callback.answer("Сохранено")


@router.callback_query(F.data == "view:settings")
async def settings_panel(
    callback: CallbackQuery, bot: Bot, settings: Settings, service: PlanningService
) -> None:
    preferences = await service.database.preferences(settings.student_id)
    await show_text(
        bot,
        service.database,
        _callback_chat_id(callback),
        render_settings(preferences),
        settings_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("setting:"))
async def ask_setting(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    service: PlanningService,
) -> None:
    if callback.from_user.id != settings.student_id:
        await callback.answer("Настройки режима меняет ученица", show_alert=True)
        return
    field = _callback_data(callback).split(":", 1)[1]
    await state.set_state(InputState.setting)
    await state.update_data(field=field)
    hint = (
        "ЧЧ:ММ, например 05:45"
        if field.endswith("time") or field.startswith("leave_")
        else "минуты от 5 до 180"
    )
    await show_text(
        bot,
        service.database,
        _callback_chat_id(callback),
        f"<b>Изменение настройки</b>\n\nПришли новое значение: {hint}.",
        cancel_keyboard(),
    )
    await callback.answer()


@router.message(InputState.setting)
async def save_setting(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    service: PlanningService,
) -> None:
    await safe_delete(bot, message.chat.id, message.message_id)
    field = str((await state.get_data())["field"])
    try:
        if field.endswith("time") or field.startswith("leave_"):
            parsed = datetime.strptime(message.text or "", "%H:%M").time()
            value: object = time(parsed.hour, parsed.minute)
        else:
            value = int(message.text or "")
            if not 5 <= value <= 180:
                raise ValueError
        await service.update_preference(settings.student_id, field, value)
    except ValueError:
        await show_text(
            bot,
            service.database,
            message.chat.id,
            "<b>Некорректное значение</b>\n\nВремя: <code>05:45</code>. Минуты: от 5 до 180.",
            cancel_keyboard(),
        )
        return
    await state.clear()
    await _today_panel(bot, message.chat.id, settings, service, False)


@router.callback_query(F.data == "input:cancel")
async def cancel_callback(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    service: PlanningService,
) -> None:
    await state.clear()
    await _today_panel(
        bot,
        _callback_chat_id(callback),
        settings,
        service,
        callback.from_user.id == settings.owner_id,
    )
    await callback.answer()


@router.message(Command("cancel"))
async def cancel_message(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    service: PlanningService,
) -> None:
    await safe_delete(bot, message.chat.id, message.message_id)
    await state.clear()
    await _today_panel(
        bot,
        message.chat.id,
        settings,
        service,
        message.from_user is not None and message.from_user.id == settings.owner_id,
    )


@router.callback_query(F.data == "sync:sotka")
async def sync_sotka(
    callback: CallbackQuery, bot: Bot, settings: Settings, service: PlanningService
) -> None:
    if callback.from_user.id != settings.owner_id:
        await callback.answer("Синхронизация доступна владельцу", show_alert=True)
        return
    if not settings.sotka_api_token:
        await callback.answer("SOTKA_API_TOKEN не настроен", show_alert=True)
        return
    day = datetime.now(settings.tz).date()
    try:
        events = await SotkaClient(settings.sotka_api_token).calendar(
            day.replace(day=1), day + timedelta(days=settings.sotka_sync_days)
        )
        await service.import_sotka_events(events)
        await service.regenerate_range(settings.student_id, day, 7)
    except (SotkaAPIError, ValueError):
        await callback.answer("API недоступен, сохранён старый кэш", show_alert=True)
        return
    await callback.answer(f"Обновлено эфиров: {len(events)}", show_alert=True)
    visible = await service.sotka_events(day - timedelta(days=7), day + timedelta(days=30))
    await show_text(
        bot,
        service.database,
        _callback_chat_id(callback),
        render_sotka(visible, settings.tz, day),
        sotka_keyboard(visible, True),
    )
