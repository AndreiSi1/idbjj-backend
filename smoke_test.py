"""Smoke-тест мультиканального FSM на sqlite. Транспорты замоканы.

Проверяет:
  1) один и тот же сценарий (согласие → меню → анкета тренера → AI → заявка)
     даёт ИДЕНТИЧНЫЙ вывод в каналах MAX и Telegram;
  2) уведомление тренеру уходит в его канал;
  3) защита рассылок: send_proactive в MAX пропускается, в Telegram отправляется.
"""
import asyncio
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["MAX_BOT_TOKEN"] = ""
os.environ["TRAINER_CHANNEL"] = "max"
os.environ["TRAINER_CHAT_ID"] = "999"

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.services.dialog as dialog
from app.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401
from app.services import broadcast, telegram_api

SENT: list[tuple[str, str, str]] = []  # (channel, ext_id, text)


async def fake_send(channel, ext_id, text, buttons=None):
    SENT.append((channel, ext_id, text))
    return True


async def fake_answer(channel, callback_id, notification=None):
    return True


async def fake_ai(mode, user_text, profile_data=None, lang=None):
    return f"[AI:{mode}] профиль={profile_data} вопрос='{user_text}'"


async def run_channel(Session, channel, ext_id):
    """Прогоняет полный сценарий и возвращает список реплик бота (только текст)."""
    start = len(SENT)

    async def feed(**kw):
        async with Session() as s:
            await dialog.handle_update(s, channel=channel, ext_id=ext_id, full_name="Тест", **kw)
            await s.commit()

    await feed(text="/start")
    await feed(callback_payload="lang:ru", callback_id="l1")
    await feed(callback_payload="consent_accept", callback_id="c1")
    await feed(callback_payload="m:trainer", callback_id="c2")
    for ans in ["белый", "6", "3", "подтянуть гард", "нет"]:
        await feed(text=ans)
    await feed(text="Как улучшить гард?")
    # генератор «План к соревнованиям» (внутри Тренера): недель → формат → цель
    await feed(callback_payload="comp:start", callback_id="cp1")
    await feed(text="8")
    await feed(callback_payload="cf:gi", callback_id="cp2")
    await feed(text="выиграть")
    await feed(callback_payload="menu", callback_id="c3")
    await feed(callback_payload="m:contact", callback_id="c4")
    await feed(callback_payload="ck:Пробное занятие", callback_id="c5")
    await feed(text="+79990001122")
    # реплики, адресованные именно этому пользователю в этом канале
    return [t for ch, eid, t in SENT[start:] if ch == channel and eid == ext_id]


async def main():
    # Патчи/настройку делаем В ТЕСТЕ, а не на уровне модуля: под pytest все
    # тестовые модули импортируются до прогона, и модульные патчи общих объектов
    # (dialog.messenger, settings) перетирали бы друг друга между тестами.
    SENT.clear()
    dialog.messenger.send_message = fake_send
    dialog.messenger.answer_callback = fake_answer
    dialog.ai.ask = fake_ai
    settings.trainer_channel = "max"
    settings.trainer_chat_id = "999"

    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("Прогон сценария в MAX…")
    max_replies = await run_channel(Session, "max", "111")
    print(f"  реплик: {len(max_replies)}")
    print("Прогон сценария в Telegram…")
    tg_replies = await run_channel(Session, "telegram", "222")
    print(f"  реплик: {len(tg_replies)}")

    assert max_replies == tg_replies, "каналы ведут себя по-разному!"
    print("✅ Вывод в MAX и Telegram идентичен")

    # уведомление тренеру (channel=max, id=999) — пришло дважды (по разу на канал)
    trainer_msgs = [t for ch, eid, t in SENT if ch == "max" and eid == "999" and "Новая заявка" in t]
    assert len(trainer_msgs) == 2, f"тренер получил {len(trainer_msgs)} уведомлений вместо 2"
    print("✅ Уведомления тренеру доставлены (вкл. пометку канала-источника)")

    # защита рассылок
    tg_calls = []
    async def fake_tg_send(ext_id, text, buttons=None):
        tg_calls.append(ext_id)
        return True
    telegram_api.send_message = fake_tg_send

    r_max = await broadcast.send_proactive("max", "111", "Напоминание")
    assert r_max is False and tg_calls == [], "проактив в MAX не должен отправляться!"
    r_tg = await broadcast.send_proactive("telegram", "222", "Напоминание")
    assert r_tg is True and tg_calls == ["222"], "проактив в Telegram должен отправиться"
    print("✅ Рассылки: MAX заблокирован (0 отправок), Telegram разрешён")

    print("\n🎉 Все проверки пройдены")


def test_smoke():
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
