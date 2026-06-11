"""Проактивные сообщения (напоминания, анонсы, реактивация).

⚠️ Бизнес-правило, зашитое в код: проактивные сообщения по таймеру/рассылке
РАЗРЕШЕНЫ ТОЛЬКО в Telegram. В MAX они запрещены правилами платформы (п.1.5),
поэтому send_proactive для канала 'max' молча пропускает отправку.

Реакция на действие пользователя (ответ в диалоге, уведомление тренеру о заявке)
— это НЕ рассылка, она идёт через app.services.messenger без ограничений.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.services import telegram_api

log = logging.getLogger(__name__)

Button = tuple[str, str]

# Каналы, где разрешены проактивные рассылки.
PROACTIVE_CHANNELS = {"telegram"}


async def send_proactive(
    channel: str, ext_id: str, text: str, buttons: list[list[Button]] | None = None
) -> bool:
    """Отправить проактивное сообщение. Для запрещённых каналов (MAX) — пропуск."""
    if channel not in PROACTIVE_CHANNELS:
        log.info("proactive skipped for channel=%s (рассылки запрещены)", channel)
        return False
    return await telegram_api.send_message(ext_id, text, buttons)


async def broadcast(
    session: AsyncSession, text: str, buttons: list[list[Button]] | None = None
) -> int:
    """Разослать текст всем, кому это разрешено (только Telegram, только с согласием).

    Возвращает число успешных отправок. Аудиторию/сегментацию можно сузить позже
    (по mode, активности и т.п.). Вызывается из планировщика (cron) — см. README.
    """
    users = (
        await session.execute(
            select(User).where(
                User.channel.in_(PROACTIVE_CHANNELS),
                User.consent_at.is_not(None),
            )
        )
    ).scalars().all()
    sent = 0
    for u in users:
        if await send_proactive(u.channel, u.ext_id, text, buttons):
            sent += 1
    log.info("broadcast: отправлено %d из %d", sent, len(users))
    return sent
