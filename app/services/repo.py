"""Доступ к БД: пользователи (мультиканально), профиль, лог сообщений."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DialogState, JournalEntry, Message, Profile, User


async def upsert_user(
    session: AsyncSession, channel: str, ext_id: str, *,
    full_name: str | None = None, source: str | None = None,
) -> User:
    user = (
        await session.execute(
            select(User).where(User.channel == channel, User.ext_id == ext_id)
        )
    ).scalar_one_or_none()
    if user is None:
        user = User(channel=channel, ext_id=ext_id, full_name=full_name, source=source)
        session.add(user)
        await session.flush()
        return user
    # Существующий: дозаполняем имя и источник, но НЕ перезаписываем (first-touch).
    changed = False
    if full_name and not user.full_name:
        user.full_name = full_name
        changed = True
    if source and not user.source:
        user.source = source
        changed = True
    if changed:
        await session.flush()
    return user


async def get_state(session: AsyncSession, user_id: int) -> DialogState:
    state = await session.get(DialogState, user_id)
    if state is None:
        state = DialogState(user_id=user_id, step="menu", mode=None, data={})
        session.add(state)
        await session.flush()
    return state


async def get_profile(session: AsyncSession, user_id: int) -> Profile:
    prof = await session.get(Profile, user_id)
    if prof is None:
        prof = Profile(user_id=user_id, trainer={}, diet={})
        session.add(prof)
        await session.flush()
    return prof


async def log_message(session: AsyncSession, user_id: int, direction: str, text: str) -> None:
    session.add(Message(user_id=user_id, direction=direction, text=text))
    await session.flush()


# ── дневник тренировок ──────────────────────────────────────────────────────────

async def add_journal_entry(session: AsyncSession, user_id: int, text: str) -> JournalEntry:
    entry = JournalEntry(user_id=user_id, text=text)
    session.add(entry)
    await session.flush()
    return entry


async def get_journal_entries(
    session: AsyncSession, user_id: int, limit: int = 15
) -> list[JournalEntry]:
    """Последние записи дневника (новые первыми)."""
    rows = (
        await session.execute(
            select(JournalEntry)
            .where(JournalEntry.user_id == user_id)
            .order_by(JournalEntry.id.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)


async def count_journal_entries(session: AsyncSession, user_id: int) -> int:
    from sqlalchemy import func as _func
    return int(
        (
            await session.execute(
                select(_func.count(JournalEntry.id)).where(JournalEntry.user_id == user_id)
            )
        ).scalar_one()
        or 0
    )
