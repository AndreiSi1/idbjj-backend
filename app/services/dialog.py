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
from app.services import ai, i18n, messenger, metrics, progress, share_card
from app.services.i18n import t
from app.services.repo import (
    add_journal_entry,
    count_journal_entries,
    count_referrals,
    count_users,
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

# Слова-выходы: распознаём на ЛЮБОМ шаге (анкета/план/дневник/контакт), чтобы юзер
# не залипал, печатая «меню/назад/отмена» вместо нажатия кнопки.
_ESCAPE_WORDS = {
    "start", "старт", "меню", "menu", "menu principal", "menú principal", "main menu",
    "главное меню", "назад", "back", "atras", "voltar", "отмена", "отменить",
    "cancel", "cancelar", "стоп", "stop", "выйти", "выход", "salir", "sair",
}


def _is_escape(text: str) -> bool:
    low = text.strip().lower().lstrip("/").strip().replace("ё", "е")
    return low in _ESCAPE_WORDS


def _menu_buttons(lang: str | None):
    return [
        [(t(lang, "btn_trainer"), "m:trainer")],
        [(t(lang, "btn_enc"), "m:enc")],
        [(t(lang, "btn_diet"), "m:diet")],
        [(t(lang, "btn_progress"), "progress")],
        [(t(lang, "btn_journal"), "journal")],
        [(t(lang, "btn_invite"), "invite")],
        [(t(lang, "btn_oss"), "oss")],
        [(t(lang, "btn_contact"), "m:contact")],
        [(t(lang, "btn_lang"), "lang_menu")],
    ]


def _hint_buttons(lang: str | None):
    return [[(t(lang, "btn_menu"), "menu")]]


def _cancel_buttons(lang: str | None):
    """Видимый выход из шага ввода (анкета/план/дневник/контакт)."""
    return [[(t(lang, "btn_cancel"), "menu")]]


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
    # Реферальный deep-link ?start=ref_<id> → кто пригласил + единый бакет источника.
    referred_by: int | None = None
    if source and source.startswith("ref_"):
        tail = source[4:]
        if tail.isdigit():
            referred_by = int(tail)
        source = "referral"
    user = await upsert_user(
        session, channel, ext_id, full_name=full_name, source=source, referred_by=referred_by
    )
    # Новый пользователь → уведомить владельца и тренера (не должно ронять онбординг).
    if getattr(user, "is_new", False):
        await _notify_new_user(session, user)
    if text:
        await log_message(session, user.id, "in", text)
    state = await get_state(session, user.id)

    # Команда /admin владельца — доступна в любом состоянии (даже в анкете).
    if text and _is_admin(user) and _is_admin_cmd(text):
        await _admin_panel(session, user)
        return

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
            await _reward_referrer(session, user)
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
    elif payload == "share:progress":
        await _share_progress(session, user, state)
    elif payload == "invite":
        await _show_invite(session, user, state)
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
    # Выход из любого шага по слову-команде (меню/назад/отмена/…) — иначе анкета и
    # другие шаги «съедают» навигационный текст как ответ.
    if _is_escape(text):
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


async def _reward_referrer(session: AsyncSession, user: User) -> None:
    """Награда пригласившему — один раз, в момент согласия нового юзера.
    Новичку — бонус, рефереру — XP + уведомление в его канал."""
    ref_id = user.referred_by
    if not ref_id or ref_id == user.id:
        return
    referrer = await session.get(User, ref_id)
    if referrer is None:
        return
    await progress.award(session, user.id, "referred_bonus")
    await progress.award(session, referrer.id, "referral")
    xp = progress.XP_EVENTS.get("referral", 0)
    try:
        await messenger.send_message(
            referrer.channel, referrer.ext_id, t(referrer.lang, "ref_reward", xp=xp)
        )
    except Exception as e:  # noqa: BLE001 — уведомление не должно ронять онбординг
        log.warning("referrer notify failed: %s", e)


async def _show_invite(session: AsyncSession, user: User, state: DialogState) -> None:
    _set(state, step="menu", mode=None, data={})
    await session.flush()
    bot_url = settings.telegram_bot_url or "https://t.me/ID_BJJ_onlinebot"
    sep = "&" if "?" in bot_url else "?"
    link = f"{bot_url}{sep}start=ref_{user.id}"
    count = await count_referrals(session, user.id)
    await _send(
        session, user,
        t(user.lang, "invite_text", link=link, count=count),
        buttons=_hint_buttons(user.lang),
    )


def _progress_buttons(lang: str | None):
    return [
        [(t(lang, "btn_share_progress"), "share:progress")],
        [(t(lang, "btn_menu"), "menu")],
    ]


async def _show_progress(session: AsyncSession, user: User, state: DialogState) -> None:
    p = await progress.get(session, user.id)
    await _send(session, user, progress.render(p, user.lang), buttons=_progress_buttons(user.lang))


async def _share_progress(session: AsyncSession, user: User, state: DialogState) -> None:
    """Карточка прогресса PNG в свой канал (Telegram). MAX/ошибка → текстовый фолбэк.
    В подписи — deep-link с меткой ?start=share (атрибуция вирусных установок)."""
    p = await progress.get(session, user.id)
    info = progress.level_info(p.xp or 0)
    belt_label = i18n.belt_label(p.belt, user.lang) if p.belt else "—"
    bot_url = settings.telegram_bot_url or "https://t.me/ID_BJJ_onlinebot"
    sep = "&" if "?" in bot_url else "?"
    caption = t(
        user.lang, "share_caption",
        belt=belt_label, title=i18n.level_title(info["level"], user.lang),
        level=info["level"], url=f"{bot_url}{sep}start=share",
    )
    image: bytes | None = None
    try:
        image = share_card.render_progress_card(
            belt=p.belt, stripes=p.stripes or 0, xp=p.xp or 0,
            name=user.full_name, lang=user.lang,
        )
    except Exception as e:  # noqa: BLE001 — рендер не должен ронять диалог
        log.warning("share card render failed: %s", e)

    sent = False
    if image is not None:
        sent = await messenger.send_photo(
            user.channel, user.ext_id, image, caption=caption,
            buttons=_hint_buttons(user.lang),
        )
        if sent:
            await log_message(session, user.id, "out", "[карточка прогресса]")
    if not sent:  # MAX или ошибка рендера/отправки — текст + ссылка
        await _send(session, user, caption, buttons=_hint_buttons(user.lang))


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
    await _send(session, user, t(user.lang, TRAINER_Q[TRAINER_FLOW[0]]), buttons=_cancel_buttons(user.lang))


async def _start_diet(session: AsyncSession, user: User, state: DialogState) -> None:
    prof = await get_profile(session, user.id)
    if prof.diet:
        await _enter_ai(session, user, state, "dietolog")
        return
    _set(state, step="diet_anketa", mode=None, data={"_i": 0})
    await session.flush()
    await _send(session, user, t(user.lang, "dt_intro"))
    await _send(session, user, t(user.lang, DIET_Q[DIET_FLOW[0]]), buttons=_cancel_buttons(user.lang))


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
        await _send(session, user, t(user.lang, qmap[flow[i]]), buttons=_cancel_buttons(user.lang))
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
    await _send(session, user, t(user.lang, "comp_q_weeks"), buttons=_cancel_buttons(user.lang))


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
    await _send(session, user, t(user.lang, "comp_q_goal"), buttons=_cancel_buttons(user.lang))


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
    await _send(session, user, t(user.lang, "jr_ask"), buttons=_cancel_buttons(user.lang))


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
    await _send(session, user, t(user.lang, "contact_phone", kind=label), buttons=_cancel_buttons(user.lang))


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


# ── админ в боте + уведомления о новых юзерах ──────────────────────────────────────

# Кому уходят уведомления о новичках: владелец (admin) + тренер. Дедуплицируем —
# если владелец и тренер совпадают по (канал, id), шлём один раз.
def _staff_targets() -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    if settings.admin_chat_id:
        targets.append((settings.admin_channel, str(settings.admin_chat_id)))
    if settings.trainer_chat_id:
        pair = (settings.trainer_channel, str(settings.trainer_chat_id))
        if pair not in targets:
            targets.append(pair)
    return targets


async def _notify_new_user(session: AsyncSession, user: User) -> None:
    """Уведомить владельца и тренера о новом пользователе. Ошибки не роняют онбординг."""
    targets = _staff_targets()
    if not targets:
        return
    try:
        total = await count_users(session)
    except Exception:  # noqa: BLE001 — счётчик не критичен
        total = 0
    who = user.full_name or user.ext_id
    text = (
        "🆕 Новый пользователь бота\n"
        f"Имя: {who}\n"
        f"Канал: {user.channel}\n"
        f"Источник: {user.source or '—'}\n"
        f"Всего пользователей: {total}"
    )
    for ch, cid in targets:
        try:
            await messenger.send_message(ch, cid, text)
        except Exception as e:  # noqa: BLE001 — уведомление не должно ронять онбординг
            log.warning("new-user notify failed for %s:%s — %s", ch, cid, e)


# Команды-синонимы для вызова админ-сводки (с / и без).
_ADMIN_CMDS = {"admin", "админ", "админка", "panel", "панель", "stats", "статистика"}


def _is_admin_cmd(text: str) -> bool:
    return text.strip().lower().lstrip("/").strip() in _ADMIN_CMDS


def _is_admin(user: User) -> bool:
    return bool(
        settings.admin_chat_id
        and user.channel == settings.admin_channel
        and str(user.ext_id) == str(settings.admin_chat_id)
    )


async def _admin_panel(session: AsyncSession, user: User) -> None:
    """Сводка KPI прямо в боте + ссылка на веб-панель (только для владельца)."""
    s = await metrics.summary(session)
    srcs = await metrics.sources(session)
    leads = await metrics.recent_leads(session, limit=5)
    base = (settings.public_base_url or "https://idbjjapp.ru").rstrip("/")
    src_lines = "\n".join(f"• {x['source']}: {x['count']}" for x in srcs[:6]) or "• —"
    lead_lines = (
        "\n".join(f"• {l['name']} — {l['kind']} ({l['phone']})" for l in leads)
        if leads else "—"
    )
    text = (
        "📊 ID BJJ — сводка\n\n"
        f"👥 Пользователей: {s['total_users']} (TG {s['telegram_users']} / MAX {s['max_users']})\n"
        f"✅ С согласием: {s['with_consent']}\n"
        f"📝 Анкеты: тренер {s['trainer_profiles']} · диета {s['diet_profiles']}\n"
        f"🎯 Лидов: {s['leads_total']}\n"
        f"💬 Сообщений: вх {s['messages_in']} / исх {s['messages_out']}\n\n"
        f"🔗 Источники:\n{src_lines}\n\n"
        f"🆕 Последние лиды:\n{lead_lines}\n\n"
        f"🖥 Веб-панель: {base}/admin"
    )
    await _send(session, user, text, buttons=_hint_buttons(user.lang))
