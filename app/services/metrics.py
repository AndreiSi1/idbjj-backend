"""Агрегаты для админ-дашборда ID BJJ. Только чтение существующих таблиц.

В отличие от «Спецы Ру» (биржа: сделки/рейтинг), здесь клубные метрики:
пользователи, каналы (MAX/Telegram), заполненные анкеты, пояса, лиды, переписка.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Lead, Message, Profile, Progress, User
from app.services import progress as progress_svc


async def _scalar(session: AsyncSession, stmt) -> int:
    return int((await session.execute(stmt)).scalar_one() or 0)


async def summary(session: AsyncSession) -> dict:
    total_users = await _scalar(session, select(func.count(User.id)))
    max_users = await _scalar(session, select(func.count(User.id)).where(User.channel == "max"))
    tg_users = await _scalar(session, select(func.count(User.id)).where(User.channel == "telegram"))
    with_consent = await _scalar(
        session, select(func.count(User.id)).where(User.consent_at.is_not(None))
    )
    leads_total = await _scalar(session, select(func.count(Lead.id)))
    msg_in = await _scalar(
        session, select(func.count(Message.id)).where(Message.direction == "in")
    )
    msg_out = await _scalar(
        session, select(func.count(Message.id)).where(Message.direction == "out")
    )

    # Заполненные анкеты — считаем в Python (JSON != {} непортируемо в SQL).
    profiles = (await session.execute(select(Profile.trainer, Profile.diet))).all()
    trainer_profiles = sum(1 for p in profiles if p.trainer)
    diet_profiles = sum(1 for p in profiles if p.diet)

    return {
        "total_users": total_users,
        "max_users": max_users,
        "telegram_users": tg_users,
        "with_consent": with_consent,
        "trainer_profiles": trainer_profiles,
        "diet_profiles": diet_profiles,
        "leads_total": leads_total,
        "messages_in": msg_in,
        "messages_out": msg_out,
    }


async def belts(session: AsyncSession) -> list[dict]:
    """Распределение по поясам (для диаграммы)."""
    rows = (
        await session.execute(
            select(Progress.belt, func.count().label("cnt")).group_by(Progress.belt)
        )
    ).all()
    out = []
    for r in rows:
        key = r.belt or "unknown"
        label = progress_svc.BELTS.get(key, ("", "Не указан"))[1] if key != "unknown" else "Не указан"
        out.append({"belt": key, "label": label, "count": int(r.cnt)})
    return out


async def sources(session: AsyncSession) -> list[dict]:
    """Откуда пришли юзеры (атрибуция deep-link). NULL → «прямой/—»."""
    rows = (
        await session.execute(
            select(User.source, func.count().label("cnt"))
            .group_by(User.source)
            .order_by(func.count().desc())
        )
    ).all()
    return [{"source": r.source or "—", "count": int(r.cnt)} for r in rows]


async def _daily(session: AsyncSession, model, days: int = 30) -> list[dict]:
    day = func.date(model.created_at).label("day")
    rows = (
        await session.execute(
            select(day, func.count().label("cnt")).group_by(day).order_by(day)
        )
    ).all()
    series = [{"date": str(r.day), "count": int(r.cnt)} for r in rows if r.day is not None]
    return series[-days:]


async def growth(session: AsyncSession, days: int = 30) -> dict:
    return {
        "users": await _daily(session, User, days),
        "leads": await _daily(session, Lead, days),
        "messages": await _daily(session, Message, days),
    }


async def recent_leads(session: AsyncSession, limit: int = 30) -> list[dict]:
    rows = (
        await session.execute(
            select(
                Lead.id, Lead.kind, Lead.phone, Lead.created_at,
                User.full_name, User.username, User.ext_id, User.channel, User.source,
            )
            .join(User, User.id == Lead.user_id)
            .order_by(Lead.id.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "phone": r.phone,
            "name": r.full_name or r.username or f"id{r.ext_id}",
            "channel": r.channel,
            "source": r.source or "—",
            "at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


async def dashboard(session: AsyncSession) -> dict:
    return {
        "summary": await summary(session),
        "growth": await growth(session),
        "belts": await belts(session),
        "sources": await sources(session),
        "recent_leads": await recent_leads(session),
    }
