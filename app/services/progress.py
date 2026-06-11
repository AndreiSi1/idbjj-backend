"""Уровень прогресса ученика: реальный пояс (ранг) + активность в боте (XP/уровни).

- Пояс берётся из анкеты тренера (поле «Пояс»), нормализуется в канонический ключ.
- XP начисляется за действия (award). Уровень считается из XP на лету (level_info).
- render() рисует карточку прогресса для раздела «Мой прогресс».
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Progress
from app.services import i18n
from app.services.i18n import t

log = logging.getLogger(__name__)

# Канонический пояс → (эмодзи, подпись). Порядок = ранг.
BELTS = {
    "white": ("⚪", "Белый пояс"),
    "blue": ("🔵", "Синий пояс"),
    "purple": ("🟣", "Фиолетовый пояс"),
    "brown": ("🟤", "Коричневый пояс"),
    "black": ("⚫", "Чёрный пояс"),
}

# Распознавание свободного текста из анкеты (RU/EN/ES/PT) → канонический ключ.
_BELT_ALIASES = {
    "бел": "white", "white": "white", "blanco": "white", "branc": "white",
    "син": "blue", "голуб": "blue", "blue": "blue", "azul": "blue",
    "фиол": "purple", "purple": "purple", "violeta": "purple", "rox": "purple",
    "корич": "brown", "brown": "brown", "marrón": "brown", "marron": "brown", "marrom": "brown",
    "чер": "black", "чёр": "black", "black": "black", "negro": "black", "pret": "black",
}

# Очки за события. Разовые события естественно случаются ~один раз (анкета не
# переспрашивается), повторяемые (вопрос AI) копят активность.
XP_EVENTS = {
    "register": 5,        # принял согласие
    "anketa_trainer": 20, # заполнил анкету тренера
    "anketa_diet": 20,    # заполнил анкету диеты
    "ai_question": 2,     # задал вопрос ассистенту
    "lead": 10,           # оставил заявку тренеру
    "comp_plan": 15,      # сгенерировал план к соревнованиям
    "journal_entry": 5,   # записал тренировку в дневник
    "referral": 25,       # привёл друга (награда рефереру)
    "referred_bonus": 10, # пришёл по приглашению (бонус новичку)
}

XP_PER_LEVEL = 100

# Названия уровневых тиров (по номеру уровня).
LEVEL_TITLES = [
    (1, "Новичок мата"),
    (3, "Боец"),
    (5, "Атлет"),
    (8, "Ветеран мата"),
    (12, "Мастер"),
]


def normalize_belt(text: str | None) -> str | None:
    if not text:
        return None
    low = text.strip().lower()
    for alias, key in _BELT_ALIASES.items():
        if low.startswith(alias) or alias in low:
            return key
    return None


def level_info(xp: int) -> dict:
    """Уровень, текущий титул, прогресс до следующего уровня."""
    level = xp // XP_PER_LEVEL + 1
    into = xp % XP_PER_LEVEL
    title = LEVEL_TITLES[0][1]
    for need, name in LEVEL_TITLES:
        if level >= need:
            title = name
    return {
        "level": level,
        "title": title,
        "xp": xp,
        "into": into,
        "to_next": XP_PER_LEVEL - into,
        "per_level": XP_PER_LEVEL,
    }


async def _get(session: AsyncSession, user_id: int) -> Progress:
    p = await session.get(Progress, user_id)
    if p is None:
        p = Progress(user_id=user_id, belt=None, stripes=0, xp=0)
        session.add(p)
        await session.flush()
    return p


async def award(session: AsyncSession, user_id: int, event: str) -> Progress:
    """Начислить XP за событие. Неизвестные события игнорируются (0 очков)."""
    p = await _get(session, user_id)
    p.xp = (p.xp or 0) + XP_EVENTS.get(event, 0)
    await session.flush()
    return p


async def set_belt(session: AsyncSession, user_id: int, belt_text: str | None) -> Progress:
    p = await _get(session, user_id)
    belt = normalize_belt(belt_text)
    if belt:
        p.belt = belt
        await session.flush()
    return p


async def get(session: AsyncSession, user_id: int) -> Progress:
    return await _get(session, user_id)


def _bar(into: int, per_level: int, width: int = 10) -> str:
    filled = round(width * into / per_level) if per_level else 0
    return "▰" * filled + "▱" * (width - filled)


def render(progress: Progress, lang: str | None = "ru") -> str:
    """Карточка прогресса для пользователя на его языке."""
    info = level_info(progress.xp or 0)
    if progress.belt and progress.belt in BELTS:
        emoji = BELTS[progress.belt][0]
        label = i18n.belt_label(progress.belt, lang)
        stripes = f" · {progress.stripes}🔸" if progress.stripes else ""
        belt_line = f"{emoji} {t(lang, 'pg_rank')}: {label}{stripes}"
    else:
        belt_line = f"⚪ {t(lang, 'pg_rank_none')}"
    title = i18n.level_title(info["level"], lang)
    return (
        f"{t(lang, 'pg_title')}\n\n"
        f"{belt_line}\n\n"
        f"🏅 {t(lang, 'pg_level')} {info['level']} — {title}\n"
        f"{_bar(info['into'], info['per_level'])}  {info['into']}/{info['per_level']} XP\n"
        f"{t(lang, 'pg_to_next')}: {info['to_next']} XP\n\n"
        f"{t(lang, 'pg_hint')}"
    )
