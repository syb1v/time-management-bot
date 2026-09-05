from __future__ import annotations

from datetime import date
from html import escape
from zoneinfo import ZoneInfo

from .models import BlockStatus, PlanBlock, SotkaEvent, UserPreferences

RU_DAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
STATUS = {
    BlockStatus.PLANNED: "○",
    BlockStatus.DONE: "●",
    BlockStatus.PARTIAL: "◐",
    BlockStatus.MOVED: "↪",
    BlockStatus.SKIPPED: "×",
}


def render_day(day: date, blocks: list[PlanBlock], timezone: ZoneInfo) -> str:
    title = f"<b>{RU_DAYS[day.weekday()]}, {day:%d.%m}</b>"
    if not blocks:
        return f"{title}\n\nПлан пока пуст."
    done = sum(block.completion_ratio for block in blocks if block.kind in ("homework", "sotka"))
    tracked = sum(1 for block in blocks if block.kind in ("homework", "sotka"))
    progress = round(done / tracked * 100) if tracked else 0
    lines = [title, f"Прогресс учёбы: <b>{progress}%</b>", ""]
    for block in blocks:
        mark = STATUS.get(BlockStatus(block.status), "○")
        start = block.start_at.astimezone(timezone)
        end = block.end_at.astimezone(timezone)
        lines.append(f"{mark} <code>{start:%H:%M}–{end:%H:%M}</code>  {escape(block.title)}")
    return "\n".join(lines)


def render_week(days: list[tuple[date, list[PlanBlock]]]) -> str:
    lines = ["<b>Неделя</b>", ""]
    for day, blocks in days:
        study = sum(
            int((b.end_at - b.start_at).total_seconds() // 60)
            for b in blocks
            if b.kind in ("homework", "sotka")
        )
        lines.append(
            f"<b>{RU_DAYS[day.weekday()]} {day:%d.%m}</b> · учёба {study // 60}ч {study % 60:02d}м"
        )
    return "\n".join(lines)


def render_settings(preferences: UserPreferences) -> str:
    return (
        "<b>Настройки режима</b>\n\n"
        f"Подъём: <code>{preferences.wake_time:%H:%M}</code>\n"
        f"Отбой: <code>{preferences.bedtime:%H:%M}</code>\n"
        f"Выход к 08:00: <code>{preferences.leave_0800:%H:%M}</code>\n"
        f"Выход к 08:50: <code>{preferences.leave_0850:%H:%M}</code>\n"
        f"Дорога домой: <b>{preferences.travel_home_minutes} мин</b>\n"
        f"Отдых: <b>{preferences.rest_minutes} мин</b>\n"
        f"Фокус / перерыв: <b>{preferences.focus_minutes} / {preferences.break_minutes} мин</b>"
    )


def render_sotka(events: list[SotkaEvent], timezone: ZoneInfo, today: date) -> str:
    if not events:
        return "<b>Сотка</b>\n\nНет эфиров в ближайшем периоде."
    viewed = sum(event.viewed for event in events)
    homework = sum(event.homework_done for event in events)
    lines = [
        "<b>Сотка · эфиры и прогресс</b>",
        f"Просмотрено: <b>{viewed}/{len(events)}</b> · домашки: <b>{homework}/{len(events)}</b>",
        "",
    ]
    teachers = {
        "Русский язык": "Даша",
        "Обществознание": "Алексей",
        "Математика": "Александр",
    }
    for event in events:
        starts = event.starts_at.astimezone(timezone) if event.starts_at else None
        when = f"{starts:%d.%m в %H:%M}" if starts else f"{event.available_on:%d.%m}"
        viewed_mark = "● просмотрено" if event.viewed else "○ не просмотрено"
        homework_mark = "● ДЗ готово" if event.homework_done else "○ ДЗ не готово"
        overdue = event.deadline is not None and event.deadline < today and not event.viewed
        debt = " · <b>просрочено</b>" if overdue else ""
        lines.extend(
            [
                f"<b>{escape(event.subject)}</b> · {teachers.get(event.subject, '')}",
                f"<code>{when}</code> · {event.duration_minutes // 60}ч "
                f"{event.duration_minutes % 60:02d}м",
                f"{viewed_mark} · {homework_mark}{debt}",
                f"Дедлайн: <b>{event.deadline:%d.%m}</b>"
                if event.deadline
                else "Дедлайн не указан",
                "",
            ]
        )
    return "\n".join(lines).rstrip()
