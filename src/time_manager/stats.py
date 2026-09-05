from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from io import BytesIO

import matplotlib
from sqlalchemy import select

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .db import Database
from .models import DailyInput, PlanBlock, SotkaEvent


@dataclass(frozen=True)
class StatsSummary:
    days: int
    planned_minutes: int
    completed_minutes: int
    average_sleep: float | None
    active_days: int
    homework_minutes: int = 0
    sotka_minutes: int = 0
    sotka_lessons: int = 0
    sotka_viewed: int = 0
    sotka_homework_done: int = 0

    @property
    def completion_percent(self) -> int:
        if not self.planned_minutes:
            return 0
        return round(self.completed_minutes / self.planned_minutes * 100)


async def build_stats(database: Database, user_id: int, end: date, days: int) -> StatsSummary:
    start = end - timedelta(days=days - 1)
    async with database.sessions() as session:
        blocks = list(
            (
                await session.execute(
                    select(PlanBlock).where(
                        PlanBlock.user_id == user_id,
                        PlanBlock.day >= start,
                        PlanBlock.day <= end,
                        PlanBlock.kind.in_(("homework", "sotka")),
                    )
                )
            ).scalars()
        )
        inputs = list(
            (
                await session.execute(
                    select(DailyInput).where(
                        DailyInput.user_id == user_id,
                        DailyInput.day >= start,
                        DailyInput.day <= end,
                        DailyInput.sleep_hours.is_not(None),
                    )
                )
            ).scalars()
        )
        sotka_events = list(
            (
                await session.execute(
                    select(SotkaEvent).where(
                        SotkaEvent.available_on >= start,
                        SotkaEvent.available_on <= end,
                        SotkaEvent.source == "api",
                    )
                )
            ).scalars()
        )
    durations = [int((b.end_at - b.start_at).total_seconds() // 60) for b in blocks]
    completed = sum(
        round(minutes * b.completion_ratio) for minutes, b in zip(durations, blocks, strict=True)
    )
    sleep_values = [x.sleep_hours for x in inputs if x.sleep_hours is not None]
    homework_minutes = sum(
        duration
        for duration, block in zip(durations, blocks, strict=True)
        if block.kind == "homework"
    )
    sotka_minutes = sum(
        duration for duration, block in zip(durations, blocks, strict=True) if block.kind == "sotka"
    )
    return StatsSummary(
        days,
        sum(durations),
        completed,
        sum(sleep_values) / len(sleep_values) if sleep_values else None,
        len({b.day for b in blocks if b.completion_ratio > 0}),
        homework_minutes,
        sotka_minutes,
        len(sotka_events),
        sum(event.viewed for event in sotka_events),
        sum(event.homework_done for event in sotka_events),
    )


def render_stats(summary: StatsSummary) -> str:
    sleep = f"{summary.average_sleep:.1f} ч" if summary.average_sleep is not None else "нет отметок"
    return (
        f"<b>Статистика за {summary.days} дней</b>\n\n"
        f"Выполнено: <b>{summary.completion_percent}%</b>\n"
        f"План: <b>{summary.planned_minutes / 60:.1f} ч</b>\n"
        f"Факт: <b>{summary.completed_minutes / 60:.1f} ч</b>\n"
        f"Активных дней: <b>{summary.active_days}</b>\n"
        f"Средний сон: <b>{sleep}</b>\n\n"
        f"Школьное ДЗ: <b>{summary.homework_minutes / 60:.1f} ч</b>\n"
        f"Сотка в плане: <b>{summary.sotka_minutes / 60:.1f} ч</b>\n"
        f"Эфиры: <b>{summary.sotka_viewed}/{summary.sotka_lessons}</b> просмотрено\n"
        f"Домашки Сотки: <b>{summary.sotka_homework_done}/{summary.sotka_lessons}</b> выполнено"
    )


def render_chart(summary: StatsSummary) -> bytes:
    figure, axis = plt.subplots(figsize=(7, 4))
    figure.patch.set_facecolor("#111827")
    axis.set_facecolor("#111827")
    values = [
        summary.planned_minutes / 60,
        summary.completed_minutes / 60,
        summary.homework_minutes / 60,
        summary.sotka_minutes / 60,
    ]
    axis.bar(
        ["План", "Факт", "Школа", "Сотка"],
        values,
        color=["#64748b", "#22c55e", "#38bdf8", "#f59e0b"],
    )
    axis.set_ylabel("Часы", color="white")
    axis.tick_params(colors="white")
    for spine in axis.spines.values():
        spine.set_visible(False)
    axis.set_title(f"Учёба за {summary.days} дней", color="white", weight="bold")
    output = BytesIO()
    figure.tight_layout()
    figure.savefig(output, format="png", dpi=140, facecolor=figure.get_facecolor())
    plt.close(figure)
    return output.getvalue()
