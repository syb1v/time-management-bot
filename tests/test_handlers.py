from datetime import UTC, datetime

from aiogram.types import CallbackQuery, Chat, Message, User

from time_manager.handlers import _callback_chat_id


def test_callback_chat_id_is_not_recursive() -> None:
    message = Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=222222222, type="private"),
    )
    callback = CallbackQuery(
        id="callback",
        from_user=User(id=222222222, is_bot=False, first_name="Owner"),
        chat_instance="chat",
        message=message,
    )
    assert _callback_chat_id(callback) == 222222222
