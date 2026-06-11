"""3 AI-ассистента ID BJJ (Тренер / Энциклопедия / Диетолог).

Заменяет Vistral/ProTalk внутри Salebot. Мультипровайдер с авто-фоллбэком:
  - openai     → api.openai.com (OPENAI_API_KEY, OPENAI_MODEL);
  - openrouter → openrouter.ai/api/v1 (OPENROUTER_API_KEY, OPENROUTER_MODEL);
  - gigachat   → Сбер GigaChat (GIGACHAT_AUTH_KEY), оплата рублями, freemium.
Основной провайдер — settings.llm_provider; остальные с заданными кредами
подключаются как авто-фоллбэк (если основной упал/кончился — отвечает резерв).

Системный промпт для каждого режима лежит в app/prompts/*.txt. Плейсхолдеры профиля
вида #{Пояс} подставляются из данных анкет (DialogState.data → Profile).

RAG: retrieve() ищет по базе знаний (app/services/rag) и подмешивает найденные
фрагменты в системный промпт.
"""
from __future__ import annotations

import logging
from pathlib import Path

from openai import AsyncOpenAI

from app.config import settings
from app.services import gigachat_client, i18n, rag

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Режим → (файл системного промпта, ключ профиля для подстановки плейсхолдеров).
MODES = {
    "trainer": ("trainer.txt", "trainer"),
    "encyclopedia": ("encyclopedia.txt", None),
    "dietolog": ("dietolog.txt", "diet"),
    # Генератор «План к соревнованиям» — одноразовый вызов из Тренера (не чат-режим).
    "comp_plan": ("comp_plan.txt", "trainer"),
    # Разбор дневника тренировок — одноразовый вызов из «Дневника» (не чат-режим).
    "journal_coach": ("journal_coach.txt", "trainer"),
    # Геймплан из дневника — карта игры (дерево позиций/переходов). Одноразовый вызов.
    "gameplan": ("gameplan.txt", "trainer"),
}

# RAG-режим для поиска по базе знаний (если отличается от ключа MODES).
# comp_plan/journal/gameplan берут ту же базу, что тренер (вкл. 02_podgotovka_k_sorevnovaniyam).
_RAG_MODE = {"comp_plan": "trainer", "journal_coach": "trainer", "gameplan": "trainer"}

_OPENROUTER_BASE = "https://openrouter.ai/api/v1"
_clients: dict[str, AsyncOpenAI] = {}
_prompt_cache: dict[str, str] = {}


def _client_for(provider: str) -> AsyncOpenAI:
    """OpenAI-совместимый клиент для openai|openrouter (кэшируется по провайдеру)."""
    if provider not in _clients:
        if provider == "openrouter":
            if not settings.openrouter_api_key:
                raise RuntimeError("OPENROUTER_API_KEY не задан в .env")
            _clients[provider] = AsyncOpenAI(
                api_key=settings.openrouter_api_key, base_url=_OPENROUTER_BASE
            )
        else:  # openai
            if not settings.openai_api_key:
                raise RuntimeError("OPENAI_API_KEY не задан в .env")
            _clients[provider] = AsyncOpenAI(api_key=settings.openai_api_key)
    return _clients[provider]


def _models_for(provider: str) -> list[str]:
    if provider == "openrouter":
        models = [settings.openrouter_model]
        for m in (settings.openrouter_fallbacks or "").split(","):
            m = m.strip()
            if m and m not in models:
                models.append(m)
        return models
    return [settings.openai_model]


def _provider_order() -> list[str]:
    """Основной провайдер + авто-фоллбэки, у которых заданы креды."""
    order = [settings.llm_provider.lower()]
    if settings.gigachat_auth_key and "gigachat" not in order:
        order.append("gigachat")
    if settings.openai_api_key and "openai" not in order and "openrouter" not in order:
        order.append("openai")
    return order


async def _provider_chat(provider: str, messages: list[dict]) -> str:
    if provider == "gigachat":
        return await gigachat_client.chat(messages)
    # openai | openrouter — общий OpenAI-совместимый путь с перебором моделей
    client = _client_for(provider)
    last_err: Exception | None = None
    for model in _models_for(provider):
        try:
            resp = await client.chat.completions.create(
                model=model, messages=messages, temperature=0.7, max_tokens=800,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:  # noqa: BLE001 — перебираем модели
            last_err = e
            log.warning("LLM %s/%s failed: %s", provider, model, e)
    raise RuntimeError(f"{provider}: {last_err}")


def _load_prompt(filename: str) -> str:
    if filename not in _prompt_cache:
        _prompt_cache[filename] = (PROMPTS_DIR / filename).read_text(encoding="utf-8")
    return _prompt_cache[filename]


# Соответствие плейсхолдеров #{...} в промптах ключам данных анкеты.
def _fill_profile(prompt: str, profile_data: dict | None) -> str:
    data = profile_data or {}
    for key, value in data.items():
        prompt = prompt.replace("#{" + key + "}", str(value))
    return prompt


async def retrieve(mode: str, query: str) -> str:
    """RAG-поиск по базе знаний (app/knowledge_base) через app.services.rag.

    У энциклопедии режим совпадает; для тренера/диетолога режим тот же ключ.
    Возвращает релевантные фрагменты или "" (тогда ассистент отвечает по промпту).
    """
    return await rag.retrieve(_RAG_MODE.get(mode, mode), query)


def build_system_prompt(mode: str, profile_data: dict | None, context: str = "", lang: str | None = None) -> str:
    filename, _ = MODES[mode]
    system = _fill_profile(_load_prompt(filename), profile_data)
    if context:
        system += f"\n\n--- МАТЕРИАЛЫ (используй только их) ---\n{context}"
    # Директиву языка ставим В НАЧАЛО (и в конец) — иначе модель отвечает на языке
    # русского контекста базы знаний.
    directive = i18n.AI_LANG.get(lang or "ru", i18n.AI_LANG["ru"])
    return f"{directive}\n\n{system}\n\n{directive}"


async def ask(mode: str, user_text: str, profile_data: dict | None = None, lang: str | None = None) -> str:
    """Главная точка входа: ответ AI-ассистента в заданном режиме на языке пользователя."""
    if mode not in MODES:
        raise ValueError(f"unknown AI mode: {mode}")

    context = await retrieve(mode, user_text)
    system = build_system_prompt(mode, profile_data, context, lang=lang)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_text},
    ]

    last_err: Exception | None = None
    for provider in _provider_order():
        try:
            return await _provider_chat(provider, messages)
        except Exception as e:  # noqa: BLE001 — фоллбэк к следующему провайдеру
            last_err = e
            log.warning("LLM provider %s failed: %s", provider, e)
    raise RuntimeError(f"Все LLM недоступны. Последняя ошибка: {last_err}")
