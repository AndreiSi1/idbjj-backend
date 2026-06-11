"""Telegram Bot API client — второй канал рядом с MAX.

Тот же абстрактный формат кнопок [[(подпись, payload)]], что и у max_api, чтобы
сценарий (dialog.py) не знал, в каком канале он работает. В отличие от MAX,
Telegram разрешает проактивные сообщения (см. app.services.broadcast).

Контракт:
  - sendMessage:        POST /bot<token>/sendMessage  {chat_id, text, reply_markup?}
  - inline-кнопки:      reply_markup {inline_keyboard: [[{text, callback_data}]]}
  - ответ на нажатие:   POST /bot<token>/answerCallbackQuery {callback_query_id, text?}
  - вебхук:             POST /bot<token>/setWebhook {url, secret_token?}
  - id сообщения:       response.result.message_id
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)

Button = tuple[str, str]


def _reply_markup(buttons: list[list[Button]] | None) -> dict[str, Any] | None:
    if not buttons:
        return None
    rows = [
        [{"text": text, "callback_data": payload} for text, payload in row]
        for row in buttons
    ]
    return {"inline_keyboard": rows}


def _url(method: str) -> str:
    return f"{settings.telegram_api_base}/bot{settings.telegram_bot_token}/{method}"


async def _post(method: str, json: dict[str, Any]) -> dict[str, Any] | None:
    if not settings.telegram_bot_token:
        log.warning("TELEGRAM_BOT_TOKEN is empty — skipping %s", method)
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            r = await http.post(_url(method), json=json)
        if r.status_code >= 400:
            log.warning("TG %s -> %s: %s", method, r.status_code, r.text[:300])
            return None
        return r.json()
    except httpx.HTTPError as e:
        log.warning("TG %s error: %s", method, e)
        return None


async def send_message(chat_id: str, text: str, buttons: list[list[Button]] | None = None) -> bool:
    body: dict[str, Any] = {"chat_id": str(chat_id), "text": text}
    markup = _reply_markup(buttons)
    if markup:
        body["reply_markup"] = markup
    resp = await _post("sendMessage", body)
    return resp is not None


async def answer_callback(callback_id: str, notification: str | None = None) -> bool:
    body: dict[str, Any] = {"callback_query_id": callback_id}
    if notification:
        body["text"] = notification
    resp = await _post("answerCallbackQuery", body)
    return resp is not None


async def set_webhook(url: str) -> bool:
    body: dict[str, Any] = {"url": url}
    if settings.telegram_webhook_secret:
        body["secret_token"] = settings.telegram_webhook_secret
    resp = await _post("setWebhook", body)
    return resp is not None


async def delete_webhook() -> bool:
    resp = await _post("deleteWebhook", {})
    return resp is not None
