"""Единый слой отправки — диспетчер по каналу пользователя.

Сценарий (dialog.py) шлёт сообщения через messenger и не знает, MAX это или
Telegram. Формат кнопок одинаковый: [[(подпись, payload)]]. Так один и тот же
бот работает идентично в обоих каналах.
"""
from __future__ import annotations

from app.services import max_api, telegram_api

Button = tuple[str, str]


async def send_message(
    channel: str, ext_id: str, text: str, buttons: list[list[Button]] | None = None
) -> bool:
    if channel == "telegram":
        return await telegram_api.send_message(ext_id, text, buttons)
    return await max_api.send_message(ext_id, text, buttons)


async def send_photo(
    channel: str, ext_id: str, image: bytes, caption: str | None = None,
    buttons: list[list[Button]] | None = None,
) -> bool:
    """Отправить картинку. Пока поддержан Telegram; для MAX возвращаем False —
    вызывающий код делает текстовый фолбэк (загрузка медиа в MAX — отдельный шаг)."""
    if channel == "telegram":
        return await telegram_api.send_photo(ext_id, image, caption, buttons)
    return False


async def answer_callback(channel: str, callback_id: str, notification: str | None = None) -> bool:
    if not callback_id:
        return False
    if channel == "telegram":
        return await telegram_api.answer_callback(callback_id, notification)
    return await max_api.answer_callback(callback_id, notification)
