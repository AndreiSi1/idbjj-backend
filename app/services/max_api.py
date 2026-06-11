"""MAX Bot API client — полностью заменяет Salebot для приёма и отправки сообщений.

Контракт MAX Bot API (botapi.max.ru):
  - авторизация: заголовок Authorization: <токен бота> (query-параметр access_token устарел);
  - отправка: POST /messages?access_token=..&user_id=.. | &chat_id=.. body {text, attachments?};
  - кнопки: attachment {type:"inline_keyboard", payload:{buttons:[[{type:"callback",text,payload}]]}};
  - ответ на нажатие: POST /answers?access_token=..&callback_id=.. body {notification?};
  - вебхук: POST /subscriptions?access_token=.. body {url};
  - id отправленного сообщения: response.message.body.mid.
Вебхук-сервер должен слушать 80/8080/443/8443/16384-32383 (на VPS — 443 за Caddy).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)

# Кнопка inline-клавиатуры: (подпись, payload-строка, которая вернётся в callback).
Button = tuple[str, str]


def _build_keyboard(buttons: list[list[Button]] | None) -> list[dict[str, Any]] | None:
    if not buttons:
        return None
    rows = [
        [{"type": "callback", "text": text, "payload": payload} for text, payload in row]
        for row in buttons
    ]
    return [{"type": "inline_keyboard", "payload": {"buttons": rows}}]


def _url(path: str) -> str:
    return f"{settings.max_api_base}{path}"


def _headers() -> dict[str, str]:
    # MAX перешёл с query-параметра access_token на заголовок Authorization (без "Bearer").
    return {"Authorization": settings.max_bot_token}


def _params(**extra: Any) -> dict[str, Any]:
    return dict(extra)


async def _post(path: str, *, params: dict[str, Any], json: dict[str, Any]) -> dict[str, Any] | None:
    if not settings.max_bot_token:
        log.warning("MAX_BOT_TOKEN is empty — skipping %s", path)
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            r = await http.post(_url(path), params=params, json=json, headers=_headers())
        if r.status_code >= 400:
            log.warning("MAX %s -> %s: %s", path, r.status_code, r.text[:300])
            return None
        return r.json()
    except httpx.HTTPError as e:
        log.warning("MAX %s error: %s", path, e)
        return None


def _extract_mid(resp: dict[str, Any] | None) -> str | None:
    if not resp:
        return None
    msg = resp.get("message") or resp
    body = msg.get("body") if isinstance(msg, dict) else None
    if isinstance(body, dict) and body.get("mid"):
        return str(body["mid"])
    return str(msg.get("mid")) if isinstance(msg, dict) and msg.get("mid") else None


async def send_message(user_id: str, text: str, buttons: list[list[Button]] | None = None) -> bool:
    """Отправить личное сообщение пользователю. Ошибки логируются, но не пробрасываются."""
    body: dict[str, Any] = {"text": text}
    kb = _build_keyboard(buttons)
    if kb:
        body["attachments"] = kb
    resp = await _post("/messages", params=_params(user_id=str(user_id)), json=body)
    return resp is not None


async def post_to_channel(text: str, buttons: list[list[Button]] | None = None) -> str | None:
    """Опубликовать пост в канал (бот должен быть его админом). Возвращает mid или None."""
    if not settings.max_channel_id:
        log.warning("MAX_CHANNEL_ID is empty — skipping channel post")
        return None
    body: dict[str, Any] = {"text": text}
    kb = _build_keyboard(buttons)
    if kb:
        body["attachments"] = kb
    resp = await _post("/messages", params=_params(chat_id=str(settings.max_channel_id)), json=body)
    return _extract_mid(resp)


async def answer_callback(callback_id: str, notification: str | None = None) -> bool:
    """Подтвердить нажатие inline-кнопки (убрать «крутилку» в MAX)."""
    body: dict[str, Any] = {}
    if notification:
        body["notification"] = notification
    resp = await _post("/answers", params=_params(callback_id=callback_id), json=body)
    return resp is not None


async def set_webhook(url: str) -> bool:
    """Подписать MAX на отправку апдейтов на наш URL вебхука."""
    resp = await _post("/subscriptions", params=_params(), json={"url": url})
    return resp is not None


async def delete_webhook(url: str) -> bool:
    if not settings.max_bot_token:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            r = await http.request("DELETE", _url("/subscriptions"), params=_params(url=url), headers=_headers())
        return r.status_code < 400
    except httpx.HTTPError as e:
        log.warning("MAX delete_webhook error: %s", e)
        return False
