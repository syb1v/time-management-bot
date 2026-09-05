from time_manager.bot import AccessMiddleware, create_dispatcher
from time_manager.config import Settings
from time_manager.db import Database
from time_manager.keyboards import home_keyboard, stats_keyboard
from time_manager.services import PlanningService


def test_home_keyboard_contains_main_actions() -> None:
    labels = [button.text for row in home_keyboard().inline_keyboard for button in row]
    assert {"Сегодня", "Неделя", "ДЗ: часы", "Сон: часы", "Статистика", "Настройки"} <= set(labels)


def test_dispatcher_has_access_middleware_and_router() -> None:
    settings = Settings(bot_token="123:test")
    database = Database("sqlite+aiosqlite:///:memory:")
    dispatcher = create_dispatcher(settings, PlanningService(database, settings.tz))
    assert any(router.name == "main" for router in dispatcher.sub_routers)
    assert AccessMiddleware(settings.allowed_ids).allowed_ids == settings.allowed_ids


def test_stats_keyboard_has_all_periods() -> None:
    labels = [button.text for row in stats_keyboard(183).inline_keyboard for button in row]
    assert {"Неделя", "Месяц", "● Полгода", "Год", "Назад"} == set(labels)
