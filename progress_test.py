"""Тест прогресса (пояс+XP), метрик дашборда и сборки FastAPI-приложения."""
import asyncio
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["ADMIN_PASSWORD"] = "secret"
os.environ["TELEGRAM_BOT_URL"] = "https://t.me/idbjj_bot"

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.services.dialog as dialog
from app.db.base import Base
from app.db import models  # noqa: F401
from app.services import metrics, progress
from app.services.repo import upsert_user


async def fake_send(channel, ext_id, text, buttons=None):
    return True
async def fake_answer(channel, cb, notification=None):
    return True
async def fake_ai(mode, t, profile_data=None, lang=None):
    return "ответ"
dialog.messenger.send_message = fake_send
dialog.messenger.answer_callback = fake_answer
dialog.ai.ask = fake_ai


async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 1) Уровни из XP
    assert progress.level_info(0)["level"] == 1
    assert progress.level_info(250)["level"] == 3 and progress.level_info(250)["into"] == 50
    assert progress.normalize_belt("Синий") == "blue"
    assert progress.normalize_belt("чёрный пояс") == "black"
    print("✅ Уровни и нормализация пояса")

    # 2) Полный путь: согласие(+5) → анкета тренера(+20, пояс) → вопрос AI(+2) → лид(+10)
    async def feed(**kw):
        async with Session() as s:
            await dialog.handle_update(s, channel="telegram", ext_id="42", full_name="Тест", **kw)
            await s.commit()

    await feed(text="/start")
    await feed(callback_payload="lang:ru", callback_id="l1")
    await feed(callback_payload="consent_accept", callback_id="c1")
    await feed(callback_payload="m:trainer", callback_id="c2")
    for ans in ["синий", "18", "4", "турнир", "колено"]:
        await feed(text=ans)
    await feed(text="Как пройти гард?")
    await feed(callback_payload="menu", callback_id="c3")
    await feed(callback_payload="m:contact", callback_id="c4")
    await feed(callback_payload="ck:Пробное занятие", callback_id="c5")
    await feed(text="+79990001122")

    async with Session() as s:
        user = await upsert_user(s, "telegram", "42")
        p = await progress.get(s, user.id)
        # 5 + 20 + 2 + 10 = 37
        assert p.xp == 37, f"xp={p.xp} (ожидалось 37)"
        assert p.belt == "blue", f"belt={p.belt}"
        card = progress.render(p)
        assert "Синий пояс" in card and "Уровень 1" in card
    print(f"✅ Прогресс: XP=37, пояс=blue, карточка рендерится")

    # 3) Метрики дашборда
    async with Session() as s:
        d = await metrics.dashboard(s)
        sm = d["summary"]
        assert sm["total_users"] == 1 and sm["telegram_users"] == 1
        assert sm["trainer_profiles"] == 1 and sm["leads_total"] == 1
        assert sm["messages_in"] > 0 and sm["messages_out"] > 0
        assert any(b["belt"] == "blue" and b["count"] == 1 for b in d["belts"])
        assert len(d["recent_leads"]) == 1
    print("✅ Метрики дашборда корректны")

    # 4) Сборка приложения + лендинг с подстановкой ссылок
    from app.main import app, landing
    paths = {r.path for r in app.routes}
    assert {"/", "/terms", "/privacy", "/admin", "/health", "/webhooks/max/{secret}", "/webhooks/telegram/{secret}"} <= paths
    html = (await landing()).body.decode()
    assert "https://t.me/idbjj_bot" in html and "{{TELEGRAM_BOT_URL}}" not in html
    assert "карман" in html and "Oss" in html
    print("✅ Приложение собрано, лендинг рендерится с реальными ссылками")

    print("\n🎉 Все проверки прогресса/панели/лендинга пройдены")


asyncio.run(main())
