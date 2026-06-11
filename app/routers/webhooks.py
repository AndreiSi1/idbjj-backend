"""Входящие вебхуки MAX и Telegram. Оба нормализуют апдейт в один вызов
dialog.handle_update(channel=...), поэтому сценарий идентичен в обоих каналах.
"""
import hmac
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import DB
from app.services import dialog

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _sanitize_source(raw: str | None) -> str | None:
    """Источник атрибуции: только [a-z0-9_-], нижний регистр, до 64 символов."""
    if not raw:
        return None
    s = "".join(c for c in raw.strip().lower() if c.isalnum() or c in "_-")
    return s[:64] or None


def _extract_source(text: str | None, payload: str | None) -> tuple[str | None, str | None]:
    """Из deep-link «/start <src>» вытащить источник и нормализовать текст до «/start».
    Если источник передан отдельно (payload, как в MAX) — берём его.
    Возвращает (text, source)."""
    source = _sanitize_source(payload)
    if text and text.startswith("/start"):
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            source = source or _sanitize_source(parts[1])
            text = "/start"
    return text, source


# ── MAX ──────────────────────────────────────────────────────────────────────────

@router.post("/max/{secret}")
async def max_webhook(secret: str, request: Request, session: AsyncSession = DB) -> dict[str, str]:
    if not settings.max_webhook_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "webhook not configured")
    if not hmac.compare_digest(secret, settings.max_webhook_secret):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "bad secret")
    try:
        update: dict[str, Any] = await request.json()
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid json")
    await _dispatch_max(session, update)
    return {"status": "ok"}


def _max_update_type(update: dict[str, Any]) -> str:
    return update.get("update_type") or next(
        (
            k
            for k in ("message_created", "message_callback", "bot_started", "bot_added", "bot_removed")
            if k in update
        ),
        "unknown",
    )


def _max_user(obj: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not isinstance(obj, dict):
        return None, None
    uid = obj.get("user_id") or obj.get("id")
    name = (
        obj.get("name")
        or " ".join(p for p in (obj.get("first_name"), obj.get("last_name")) if p)
        or obj.get("username")
    )
    return (str(uid) if uid is not None else None), (name or None)


async def _dispatch_max(session: AsyncSession, update: dict[str, Any]) -> None:
    utype = _max_update_type(update)
    log.info("max update: %s", utype)

    if utype == "message_callback":
        cb = update.get("callback") or {}
        ext_id, full_name = _max_user(cb.get("user") or update.get("user"))
        if not ext_id:
            return
        await dialog.handle_update(
            session, channel="max", ext_id=ext_id, full_name=full_name,
            callback_payload=cb.get("payload", ""), callback_id=cb.get("callback_id"),
        )
        return

    if utype in ("message_created", "bot_started"):
        message = update.get("message") or {}
        sender = message.get("sender") or update.get("user")
        ext_id, full_name = _max_user(sender)
        if not ext_id:
            return
        body = message.get("body") or {}
        text = body.get("text") if isinstance(body, dict) else None
        # MAX: payload deep-link приходит в bot_started (атрибуция источника).
        source = update.get("payload") if utype == "bot_started" else None
        text, source = _extract_source(text, source)
        await dialog.handle_update(
            session, channel="max", ext_id=ext_id, full_name=full_name,
            text=text if text is not None else "/start", source=source,
        )
        return
    # bot_added / bot_removed / unknown — игнорируем


# ── Telegram ───────────────────────────────────────────────────────────────────────

@router.post("/telegram/{secret}")
async def telegram_webhook(
    secret: str,
    request: Request,
    session: AsyncSession = DB,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, str]:
    if not settings.telegram_webhook_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "webhook not configured")
    # Telegram дублирует секрет и в URL, и в заголовке — проверяем оба, что совпало.
    token = x_telegram_bot_api_secret_token or secret
    if not hmac.compare_digest(token, settings.telegram_webhook_secret):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "bad secret")
    try:
        update: dict[str, Any] = await request.json()
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid json")
    await _dispatch_telegram(session, update)
    return {"status": "ok"}


def _tg_user(frm: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not isinstance(frm, dict):
        return None, None
    uid = frm.get("id")
    name = " ".join(p for p in (frm.get("first_name"), frm.get("last_name")) if p) or frm.get("username")
    return (str(uid) if uid is not None else None), (name or None)


async def _dispatch_telegram(session: AsyncSession, update: dict[str, Any]) -> None:
    if "callback_query" in update:
        cb = update["callback_query"] or {}
        ext_id, full_name = _tg_user(cb.get("from"))
        if not ext_id:
            return
        await dialog.handle_update(
            session, channel="telegram", ext_id=ext_id, full_name=full_name,
            callback_payload=cb.get("data", ""), callback_id=str(cb.get("id")) if cb.get("id") else None,
        )
        return

    message = update.get("message") or update.get("edited_message")
    if message:
        ext_id, full_name = _tg_user(message.get("from"))
        if not ext_id:
            return
        text = message.get("text")
        # Telegram: deep-link «/start <payload>» — извлекаем источник, текст нормализуем.
        text, source = _extract_source(text, None)
        # /start без текста и прочие служебные — трактуем как меню
        await dialog.handle_update(
            session, channel="telegram", ext_id=ext_id, full_name=full_name,
            text=text if text is not None else "/start", source=source,
        )
        return
    log.info("telegram update ignored (no message/callback)")
