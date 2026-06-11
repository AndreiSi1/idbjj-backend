"""GigaChat (Сбер) клиент — оплата рублями, freemium 1M токенов/мес.

Портирован из проекта sidorenko-sales. Поток: получить OAuth access_token по
Basic-ключу (кэшируется до истечения) → POST в chat/completions с Bearer-токеном.
verify=False — у Sber своя цепочка сертификатов (как в рабочем sidorenko-sales).
"""
from __future__ import annotations

import logging
import time
import uuid

import httpx

from app.config import settings

log = logging.getLogger(__name__)

_OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
_API_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

_token: str | None = None
_expires_at: float = 0.0


async def _refresh_token() -> str:
    global _token, _expires_at
    async with httpx.AsyncClient(verify=False, timeout=30) as http:
        r = await http.post(
            _OAUTH_URL,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "RqUID": str(uuid.uuid4()),
                "Authorization": f"Basic {settings.gigachat_auth_key}",
            },
            data={"scope": settings.gigachat_scope},
        )
        r.raise_for_status()
        payload = r.json()
    _token = payload["access_token"]
    _expires_at = (payload["expires_at"] / 1000) - 60
    return _token


async def _ensure_token() -> str:
    if not _token or time.time() >= _expires_at:
        return await _refresh_token()
    return _token


async def chat(
    messages: list[dict],
    *,
    temperature: float = 0.7,
    max_tokens: int = 800,
) -> str:
    if not settings.gigachat_auth_key:
        raise RuntimeError("GIGACHAT_AUTH_KEY не задан")
    token = await _ensure_token()
    async with httpx.AsyncClient(verify=False, timeout=60) as http:
        r = await http.post(
            _API_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "model": settings.gigachat_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        r.raise_for_status()
        payload = r.json()
    return (payload["choices"][0]["message"]["content"] or "").strip()
