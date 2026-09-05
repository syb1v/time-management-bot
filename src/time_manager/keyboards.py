from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .models import PlanBlock, SotkaEvent


def home_keyboard(owner: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Сегодня", callback_data="view:today"),
        InlineKeyboardButton(text="Неделя", callback_data="view:week"),
    )
    builder.row(
        InlineKeyboardButton(text="Отметиться", callback_data="view:checkin"),
        InlineKeyboardButton(text="ДЗ: часы", callback_data="input:homework"),
    )
    builder.row(
        InlineKeyboardButton(text="Сотка", callback_data="view:sotka"),
        InlineKeyboardButton(text="Статистика", callback_data="view:stats"),
    )
    if not owner:
        builder.row(InlineKeyboardButton(text="Сон: часы", callback_data="input:sleep"))
    builder.row(InlineKeyboardButton(text="Настройки", callback_data="view:settings"))
    if owner:
        builder.row(InlineKeyboardButton(text="Обновить Сотку", callback_data="sync:sotka"))
    return builder.as_markup()


def blocks_keyboard(blocks: list[PlanBlock]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for block in blocks:
        if block.kind not in ("homework", "sotka"):
            continue
        builder.row(
            InlineKeyboardButton(
                text=f"Готово: {block.title[:18]}", callback_data=f"done:{block.id}"
            ),
            InlineKeyboardButton(text="50%", callback_data=f"partial:{block.id}"),
            InlineKeyboardButton(text="Перенести", callback_data=f"move:{block.id}"),
            InlineKeyboardButton(text="Пропустить", callback_data=f"skip:{block.id}"),
        )
    builder.row(InlineKeyboardButton(text="Назад", callback_data="view:today"))
    return builder.as_markup()


def settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for label, field in (
        ("Подъём", "wake_time"),
        ("Отбой", "bedtime"),
        ("Выход к 08:00", "leave_0800"),
        ("Выход к 08:50", "leave_0850"),
        ("Дорога домой", "travel_home_minutes"),
        ("Отдых", "rest_minutes"),
        ("Фокус-блок", "focus_minutes"),
        ("Перерыв", "break_minutes"),
    ):
        builder.button(text=label, callback_data=f"setting:{field}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="Назад", callback_data="view:today"))
    return builder.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="input:cancel")]]
    )


def stats_keyboard(selected: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for label, days in (("Неделя", 7), ("Месяц", 30), ("Полгода", 183), ("Год", 365)):
        prefix = "● " if days == selected else ""
        builder.button(text=f"{prefix}{label}", callback_data=f"stats:{days}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="Назад", callback_data="view:today"))
    return builder.as_markup()


def sotka_keyboard(events: list[SotkaEvent], owner: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for event in events:
        if event.lesson_url and event.lesson_id:
            builder.row(
                InlineKeyboardButton(
                    text=f"Открыть · {event.subject} · {event.available_on:%d.%m}",
                    url=event.lesson_url,
                )
            )
    if owner:
        builder.row(InlineKeyboardButton(text="Обновить Сотку", callback_data="sync:sotka"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="view:today"))
    return builder.as_markup()
