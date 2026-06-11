"""FSM диалога ID BJJ — заменяет визуальную воронку Salebot. Мультиязычный (RU/EN/ES/PT).

Поток: выбор языка → согласие (152-ФЗ) → меню (ядро: Тренер / Энциклопедия / Диета /
Прогресс / Oss-скоро / Связь) → анкеты / AI-режимы. Все строки UI берутся через
i18n.t(user.lang, key); AI отвечает на языке пользователя.

`mode` (trainer/encyclopedia/dietolog) заменяет метки Salebot: когда он выставлен,
текст пользователя уходит соответствующему AI-ассистенту.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import DialogState, Lead, User
from app.services import ai, i18n, messenger, progress
from app.services.i18n import t
from app.services.repo import (
    add_journal_entry,
    count_journal_entries,
    get_journal_entries,
    get_profile,
    get_state,
    log_message,
    upsert_user,
)

log = logging.getLogger(__name__)

# ── анкеты: канонические ключи полей (совпадают с #{плейсхолдерами} промптов) ──────
TRAINER_FLOW = ["Пояс", "Стаж", "Частота", "Цель", "Травмы"]
TRAINER_Q = {
    "Пояс": "tr_q_belt", "Стаж": "tr_q_exp", "Частота": "tr_q_freq",
    "Цель": "tr_q_goal", "Травмы": "tr_q_injury",
}
DIET_FLOW = ["Пол", "Возраст", "Рост", "Вес", "Активность", "Цель_диеты"]
DIET_Q = {
    "Пол": "dt_q_sex", "Возраст": "dt_q_age", "Рост": "dt_q_height",
    "Вес": "dt_q_weight", "Активность": "dt_q_activity", "Цель_диеты": "dt_q_goal",
}

# Типы заявок: ключ → подпись для тренера/админки (RU) — единый учёт.
CONTACT_KIND_RU = {"trial": "Пробное занятие", "question": "Вопрос тренеру", "sub": "Абонемент / цены"}

# Генератор «План к соревнованиям»: формат турнира — канонические значения для промпта.
COMP_FORMAT_RU = {"gi": "Gi (в кимоно)", "nogi": "No-Gi (без кимоно)", "both": "Gi + No-Gi"}


def _menu_buttons(lang: str | None):
    return [
        [(t(lang, "btn_trainer"), "m:trainer")],
        [(t(lang, "btn_enc"), "m:enc")],
        [(t(lang, "btn_diet"), "m:diet")],
        [(t(lang, "btn_progress"), "progress")],
        [(t(lang, "btn_journal"), "journal")],
        [(t(lang, "btn_oss"), "oss")],
        [(t(lang, "btn_contact"), "m:contact")],
        [(t(lang, "btn_lang"), "lang_menu")],
    ]


def _hint_buttons(lang: str | None):
    return [[(t(lang, "btn_menu"), "menu")]]


def _trainer_buttons(lang: str | None):
    """Под чатом с тренером — запуск генератора плана + выход в меню."""
    return [
        [(t(lang, "btn_comp"), "comp:start")],
        [(t(lang, "btn_menu"), "menu")],
    ]


def _comp_format_buttons(lang: str | None):
    return [
        [(t(lang, "cf_gi"), "cf:gi")],
        [(t(lang, "cf_nogi"), "cf:nogi")],
        [(t(lang, "cf_both"), "cf:both")],
    ]


def _contact_kinds(lang: str | None):
    return [
        [(t(lang, "ck_trial"), "ck:trial")],
        [(t(lang, "ck_question"), "ck:question")],
        [(t(lang, "ck_sub"), "ck:sub")],
    ]


# ── низкоуровневые помощники ──────────────────────────────────────────────────────

async def _send(session: AsyncSession, user: User, text: str, buttons=None) -> None:
    await messenger.send_message(user.channel, user.ext_id, text, buttons=buttons)
    await log_message(session, user.id, "out", text)


def _set(state: DialogState, *, step: str, mode: str | None = None, data: dict | None = None) -> None:
    state.step = step
    state.mode = mode
    state.data = data if data is not None else {}


async def _send_consent(session: AsyncSession, user: User) -> None:
    base = (settings.public_base_url or "https://idbjjapp.ru").rstrip("/")
    text = t(user.lang, "consent", terms=f"{base}/terms", privacy=f"{base}/privacy")
    await _send(session, user, text, buttons=[[(t(user.lang, "btn_accept"), "consent_accept")]])


# ── точка входа ─────────────────────────────────────────────────────────────────

async def handle_update(
    session: AsyncSession,
    *,
    channel: str,
    ext_id: str,
    full_name: str | None = None,
    text: str | None = None,
    callback_payload: str | None = None,
    callback_id: str | None = None,
    source: str | None = None,
) -> None:
    user = await upsert_user(session, channel, ext_id, full_name=full_name, source=source)
    if text:
        await log_message(session, user.id, "in", text)
    state = await get_state(session, user.id)

    # 1) Язык ещё не выбран — пускаем только выбор языка.
    if user.lang is None:
        if callback_id:
            await messenger.answer_callback(user.channel, callback_id)
        if callback_payload and callback_payload.startswith("lang:"):
            choice = callback_payload.split(":", 1)[1]
            user.lang = choice if choice in i18n.LANGS else i18n.DEFAULT_LANG
            await session.flush()
            # уже принявшие согласие (старые юзеры) → сразу меню, остальные → оферта
            if user.consent_at is not None:
                await _show_menu(session, user, state)
            else:
                await _send_consent(session, user)
        else:
            await _send(session, user, i18n.LANG_PROMPT, buttons=i18n.LANG_BUTTONS)
        return

    # 2) Согласие 152-ФЗ.
    if user.consent_at is None:
        if callback_id:
            await messenger.answer_callback(user.channel, callback_id)
        if callback_payload == "consent_accept":
            user.consent_at = datetime.now(timezone.utc)
            await session.flush()
            await progress.award(session, user.id, "register")
            await _show_menu(session, user, state)
        else:
            await _send_consent(session, user)
        return

    # 3) Обычный поток.
    if callback_payload is not None:
        if callback_id:
            await messenger.answer_callback(user.channel, callback_id)
        await _handle_callback(session, user, state, callback_payload)
        return

    await _handle_text(session, user, state, (text or "").strip())


# ── callbacks (кнопки) ───────────────────────────────────────────────────────────

async def _handle_callback(session: AsyncSession, user: User, state: DialogState, payload: str) -> None:
    if payload in ("menu", "m:back"):
        await _show_menu(session, user, state)
    elif payload == "m:trainer":
        await _start_trainer(session, user, state)
    elif payload == "m:enc":
        await _enter_ai(session, user, state, "encyclopedia")
    elif payload == "m:diet":
        await _start_diet(session, user, state)
    elif payload == "progress":
        await _show_progress(session, user, state)
    elif payload == "journal":
        await _show_journal(session, user, state)
    elif payload == "jr:add":
        await _journal_add(session, user, state)
    elif payload == "jr:review":
        await _journal_review(session, user, state)
    elif payload == "jr:plan":
        await _journal_gameplan(session, user, state)
    elif payload == "oss":
        await _show_oss(session, user, state)
    elif payload == "m:contact":
        await _start_contact(session, user, state)
    elif payload.startswith("ck:"):
        await _contact_kind(session, user, state, payload.split(":", 1)[1])
    elif payload == "comp:start":
        await _start_comp(session, user, state)
    elif payload.startswith("cf:"):
        await _comp_format(session, user, state, payload.split(":", 1)[1])
    elif payload == "lang_menu":
        await _send(session, user, i18n.LANG_PROMPT, buttons=i18n.LANG_BUTTONS)
    elif payload.startswith("lang:"):
        await _change_lang(session, user, state, payload.split(":", 1)[1])
    else:
        log.info("unknown callback payload: %s", payload)
        await _show_menu(session, user, state)


# ── текст ─────────────────────────────────────────────────────────────────────────

async def _handle_text(session: AsyncSession, user: User, state: DialogState, text: str) -> None:
    low = text.lower()
    if low in ("/start", "start", "старт", "меню", "menu", "/menu", "menú", "menú principal"):
        await _show_menu(session, user, state)
        return

    if state.step == "trainer_anketa":
        await _collect_anketa(session, user, state, text, TRAINER_FLOW, TRAINER_Q, "trainer")
        return
    if state.step == "diet_anketa":
        await _collect_anketa(session, user, state, text, DIET_FLOW, DIET_Q, "diet")
        return
    if state.step == "contact_phone":
        await _collect_phone(session, user, state, text)
        return
    if state.step == "comp_weeks":
        await _collect_comp_weeks(session, user, state, text)
        return
    if state.step == "comp_goal":
        await _collect_comp_goal(session, user, state, text)
        return
    if state.step == "journal_write":
        await _collect_journal(session, user, state, text)
        return

    if state.mode in ai.MODES:
        await _ai_reply(session, user, state, text)
        return

    await _show_menu(session, user, state)


# ── меню / прогресс ───────────────────────────────────────────────────────────────

async def _show_menu(session: AsyncSession, user: User, state: DialogState) -> None:
    _set(state, step="menu", mode=None, data={})
    await session.flush()
    await _send(session, user, t(user.lang, "menu_text"), buttons=_menu_buttons(user.lang))


async def _change_lang(session: AsyncSession, user: User, state: DialogState, choice: str) -> None:
    """Смена языка уже выбравшим (из меню). Подтверждаем на НОВОМ языке и в меню."""
    user.lang = choice if choice in i18n.LANGS else i18n.DEFAULT_LANG
    await session.flush()
    await _send(session, user, t(user.lang, "lang_changed"))
    await _show_menu(session, user, state)


async def _show_progress(session: AsyncSession, user: User, state: DialogState) -> None:
    p = await progress.get(session, user.id)
    await _send(session, user, progress.render(p, user.lang), buttons=_hint_buttons(user.lang))


# ── AI-режимы ──────────────────────────────────────────────────────────────────────

async def _enter_ai(session: AsyncSession, user: User, state: DialogState, mode: str) -> None:
    _set(state, step="ai", mode=mode, data={})
    await session.flush()
    buttons = _trainer_buttons(user.lang) if mode == "trainer" else _hint_buttons(user.lang)
    await _send(session, user, t(user.lang, f"greet_{mode}"), buttons=buttons)


async def _ai_reply(session: AsyncSession, user: User, state: DialogState, text: str) -> None:
    prof = await get_profile(session, user.id)
    profile_data = prof.trainer if state.mode == "trainer" else prof.diet if state.mode == "dietolog" else {}
    try:
        answer = await ai.ask(state.mode, text, profile_data=profile_data, lang=user.lang)
    except Exception as e:  # noqa: BLE001
        log.warning("AI error: %s", e)
        answer = t(user.lang, "ai_unavailable")
    await progress.award(session, user.id, "ai_question")
    buttons = _trainer_buttons(user.lang) if state.mode == "trainer" else _hint_buttons(user.lang)
    await _send(session, user, answer, buttons=buttons)


# ── анкеты ──────────────────────────────────────────────────────────────────────

async def _start_trainer(session: AsyncSession, user: User, state: DialogState) -> None:
    prof = await get_profile(session, user.id)
    if prof.trainer:
        await _enter_ai(session, user, state, "trainer")
        return
    _set(state, step="trainer_anketa", mode=None, data={"_i": 0})
    await session.flush()
    await _send(session, user, t(user.lang, "tr_intro"))
    await _send(session, user, t(user.lang, TRAINER_Q[TRAINER_FLOW[0]]))


async def _start_diet(session: AsyncSession, user: User, state: DialogState) -> None:
    prof = await get_profile(session, user.id)
    if prof.diet:
        await _enter_ai(session, user, state, "dietolog")
        return
    _set(state, step="diet_anketa", mode=None, data={"_i": 0})
    await session.flush()
    await _send(session, user, t(user.lang, "dt_intro"))
    await _send(session, user, t(user.lang, DIET_Q[DIET_FLOW[0]]))


async def _collect_anketa(
    session: AsyncSession, user: User, state: DialogState,
    text: str, flow: list[str], qmap: dict[str, str], profile_attr: str,
) -> None:
    data = dict(state.data or {})
    i = int(data.get("_i", 0))
    data[flow[i]] = text
    i += 1
    if i < len(flow):
        data["_i"] = i
        state.data = data
        await session.flush()
        await _send(session, user, t(user.lang, qmap[flow[i]]))
        return
    # анкета собрана
    data.pop("_i", None)
    prof = await get_profile(session, user.id)
    setattr(prof, profile_attr, data)
    await session.flush()
    if profile_attr == "trainer":
        await progress.set_belt(session, user.id, data.get("Пояс"))
        await progress.award(session, user.id, "anketa_trainer")
    else:
        await progress.award(session, user.id, "anketa_diet")
    mode = "trainer" if profile_attr == "trainer" else "dietolog"
    await _send(session, user, t(user.lang, "anketa_saved"))
    await _enter_ai(session, user, state, mode)
    if mode == "dietolog":
        await _ai_reply(session, user, state, t(user.lang, "diet_calc"))


# ── генератор «План к соревнованиям» (внутри Тренера) ─────────────────────────────

async def _start_comp(session: AsyncSession, user: User, state: DialogState) -> None:
    """Мини-анкета турнира: недель → формат → цель. План строится по профилю тренера."""
    _set(state, step="comp_weeks", mode=None, data={})
    await session.flush()
    await _send(session, user, t(user.lang, "comp_intro"))
    await _send(session, user, t(user.lang, "comp_q_weeks"))


async def _collect_comp_weeks(session: AsyncSession, user: User, state: DialogState, text: str) -> None:
    data = dict(state.data or {})
    data["Недель"] = text
    _set(state, step="comp_format", mode=None, data=data)
    await session.flush()
    await _send(session, user, t(user.lang, "comp_q_format"), buttons=_comp_format_buttons(user.lang))


async def _comp_format(session: AsyncSession, user: User, state: DialogState, fmt_key: str) -> None:
    # Формат приходит кнопкой только на шаге выбора формата — иначе игнорируем.
    if state.step != "comp_format":
        await _show_menu(session, user, state)
        return
    data = dict(state.data or {})
    data["Формат"] = COMP_FORMAT_RU.get(fmt_key, fmt_key)
    _set(state, step="comp_goal", mode=None, data=data)
    await session.flush()
    await _send(session, user, t(user.lang, "comp_q_goal"))


async def _collect_comp_goal(session: AsyncSession, user: User, state: DialogState, text: str) -> None:
    data = dict(state.data or {})
    data["Цель_турнир"] = text
    await _send(session, user, t(user.lang, "comp_generating"))

    prof = await get_profile(session, user.id)
    profile_data = dict(prof.trainer or {})  # пояс/стаж/частота/травмы, если анкета пройдена
    profile_data.update({
        "Недель": data.get("Недель", ""),
        "Формат": data.get("Формат", ""),
        "Цель_турнир": data.get("Цель_турнир", ""),
    })
    try:
        answer = await ai.ask("comp_plan", t(user.lang, "comp_user_req"), profile_data=profile_data, lang=user.lang)
    except Exception as e:  # noqa: BLE001
        log.warning("comp_plan AI error: %s", e)
        answer = t(user.lang, "ai_unavailable")
    await progress.award(session, user.id, "comp_plan")

    # После плана возвращаем пользователя в чат с тренером.
    _set(state, step="ai", mode="trainer", data={})
    await session.flush()
    await _send(session, user, answer, buttons=_trainer_buttons(user.lang))


# ── Дневник тренировок ─────────────────────────────────────────────────────────────

def _journal_buttons(lang: str | None, *, has_entries: bool):
    rows = [[(t(lang, "btn_jr_add"), "jr:add")]]
    if has_entries:
        rows.append([(t(lang, "btn_jr_review"), "jr:review")])
        rows.append([(t(lang, "btn_jr_plan"), "jr:plan")])
    rows.append([(t(lang, "btn_menu"), "menu")])
    return rows


async def _show_journal(session: AsyncSession, user: User, state: DialogState) -> None:
    _set(state, step="menu", mode=None, data={})
    entries = await get_journal_entries(session, user.id, limit=5)
    await session.flush()
    if not entries:
        text = f"{t(user.lang, 'jr_title')}\n\n{t(user.lang, 'jr_empty')}"
    else:
        total = await count_journal_entries(session, user.id)
        lines = "\n".join(f"• {e.created_at:%d.%m} — {e.text[:80]}" for e in entries)
        text = (
            f"{t(user.lang, 'jr_title')}\n\n{t(user.lang, 'jr_count', n=total)}\n\n"
            f"{t(user.lang, 'jr_recent')}\n{lines}"
        )
    await _send(session, user, text, buttons=_journal_buttons(user.lang, has_entries=bool(entries)))


async def _journal_add(session: AsyncSession, user: User, state: DialogState) -> None:
    _set(state, step="journal_write", mode=None, data={})
    await session.flush()
    await _send(session, user, t(user.lang, "jr_ask"))


async def _collect_journal(session: AsyncSession, user: User, state: DialogState, text: str) -> None:
    await add_journal_entry(session, user.id, text[:1000])
    await progress.award(session, user.id, "journal_entry")
    total = await count_journal_entries(session, user.id)
    _set(state, step="menu", mode=None, data={})
    await session.flush()
    await _send(session, user, t(user.lang, "jr_saved", n=total))
    await _show_journal(session, user, state)


async def _journal_ai(
    session: AsyncSession, user: User, state: DialogState,
    *, ai_mode: str, wait_key: str, req_key: str,
) -> None:
    """Общий путь для «Разбор» и «Геймплан»: дневник + профиль → AI-режим."""
    entries = await get_journal_entries(session, user.id, limit=15)
    if not entries:
        await _send(session, user, t(user.lang, "jr_need_entries"))
        await _show_journal(session, user, state)
        return
    await _send(session, user, t(user.lang, wait_key))
    prof = await get_profile(session, user.id)
    profile_data = dict(prof.trainer or {})
    journal_text = "\n".join(f"- {e.created_at:%d.%m}: {e.text}" for e in entries)
    user_req = f"{t(user.lang, req_key)}\n\n{journal_text}"
    try:
        answer = await ai.ask(ai_mode, user_req, profile_data=profile_data, lang=user.lang)
    except Exception as e:  # noqa: BLE001
        log.warning("journal %s error: %s", ai_mode, e)
        answer = t(user.lang, "ai_unavailable")
    _set(state, step="menu", mode=None, data={})
    await session.flush()
    await _send(session, user, answer, buttons=_journal_buttons(user.lang, has_entries=True))


async def _journal_review(session: AsyncSession, user: User, state: DialogState) -> None:
    await _journal_ai(
        session, user, state,
        ai_mode="journal_coach", wait_key="jr_review_wait", req_key="jr_user_req",
    )


async def _journal_gameplan(session: AsyncSession, user: User, state: DialogState) -> None:
    await _journal_ai(
        session, user, state,
        ai_mode="gameplan", wait_key="jr_plan_wait", req_key="jr_plan_req",
    )


# ── Oss (заглушка «скоро») ───────────────────────────────────────────────────────

async def _show_oss(session: AsyncSession, user: User, state: DialogState) -> None:
    _set(state, step="menu", mode=None, data={})
    await session.flush()
    await _send(session, user, t(user.lang, "oss_text"), buttons=_hint_buttons(user.lang))


# ── связаться с тренером ───────────────────────────────────────────────────────────

async def _start_contact(session: AsyncSession, user: User, state: DialogState) -> None:
    _set(state, step="contact_kind", mode=None, data={})
    await session.flush()
    await _send(session, user, t(user.lang, "contact_ask"), buttons=_contact_kinds(user.lang))


async def _contact_kind(session: AsyncSession, user: User, state: DialogState, kind_key: str) -> None:
    _set(state, step="contact_phone", mode=None, data={"kind": kind_key})
    await session.flush()
    label = t(user.lang, f"ck_{kind_key}") if kind_key in ("trial", "question", "sub") else kind_key
    await _send(session, user, t(user.lang, "contact_phone", kind=label))


async def _collect_phone(session: AsyncSession, user: User, state: DialogState, text: str) -> None:
    kind_key = (state.data or {}).get("kind", "question")
    kind_ru = CONTACT_KIND_RU.get(kind_key, kind_key)
    session.add(Lead(user_id=user.id, kind=kind_ru, phone=text))
    await session.flush()
    await progress.award(session, user.id, "lead")
    await _notify_trainer(user, kind_ru, text)
    _set(state, step="menu", mode=None, data={})
    await session.flush()
    await _send(session, user, t(user.lang, "contact_done"), buttons=_menu_buttons(user.lang))


async def _notify_trainer(user: User, kind: str, phone: str) -> None:
    """Заявку тренеру в ЛС (на RU — тренер русскоязычный). Пусто → пропуск."""
    if not settings.trainer_chat_id:
        return
    who = user.full_name or user.ext_id
    text = (
        f"🔔 Новая заявка из бота ({user.channel}, язык: {user.lang})\n"
        f"Тип: {kind}\nОт: {who}\n📞 {phone}"
    )
    await messenger.send_message(settings.trainer_channel, settings.trainer_chat_id, text)
