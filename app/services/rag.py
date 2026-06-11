"""RAG по базе знаний ID BJJ (app/knowledge_base).

Чанкинг: каждый .txt режется на секции по Markdown-заголовкам `##`; заголовок
файла (`#`) добавляется в каждый чанк как контекст. Папки → режимы ассистентов.

Поиск двухрежимный:
  1. Векторный — если есть собранный индекс `app/rag_index.json` (см.
     scripts/build_index.py) и доступен OpenAI-эмбеддер: косинус по top-k.
  2. Keyword-фолбэк — работает офлайн без индекса/ключа (частотный матч по словам).

`retrieve()` возвращает склеенный текст найденных фрагментов (или "" если ничего).
"""
from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path

from openai import AsyncOpenAI

from app.config import settings

log = logging.getLogger(__name__)

KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"
INDEX_PATH = Path(__file__).resolve().parent.parent / "rag_index.json"
EMBED_MODEL = "text-embedding-3-small"
MAX_CONTEXT_CHARS = 3500

# Папка базы знаний → режим ассистента.
MODE_DIRS = {
    "encyclopedia": ["01_entsiklopediya"],
    "trainer": ["02_podgotovka_k_sorevnovaniyam", "04_online_trener"],
    "dietolog": ["03_dieta"],
}
_DIR_MODE = {d: m for m, dirs in MODE_DIRS.items() for d in dirs}

_STOPWORDS = {
    "для", "как", "что", "это", "при", "или", "the", "and", "под", "над", "без",
    "его", "так", "уже", "там", "тут", "вот", "все", "всё", "был", "может",
}

_chunks_cache: list[dict] | None = None
_index_cache: list[dict] | None = None
_client: AsyncOpenAI | None = None


# ── чанкинг ────────────────────────────────────────────────────────────────────

def _split_sections(text: str) -> list[tuple[str, str]]:
    """Режет markdown на (заголовок_файла, секция). Секции — по `## `."""
    lines = text.splitlines()
    file_title = ""
    for ln in lines:
        if ln.startswith("# "):
            file_title = ln[2:].strip()
            break

    sections: list[str] = []
    buf: list[str] = []
    for ln in lines:
        if ln.startswith("## "):
            if buf:
                sections.append("\n".join(buf).strip())
            buf = [ln]
        else:
            buf.append(ln)
    if buf:
        sections.append("\n".join(buf).strip())

    out: list[tuple[str, str]] = []
    for sec in sections:
        sec = sec.strip()
        # выкидываем разделители и пустышки
        sec = re.sub(r"\n-{3,}\n", "\n", sec).strip("-\n ")
        if len(sec) < 20:
            continue
        out.append((file_title, sec))
    return out


def load_chunks() -> list[dict]:
    """Все чанки базы: [{mode, source, title, text}]. Кэшируется."""
    global _chunks_cache
    if _chunks_cache is not None:
        return _chunks_cache
    chunks: list[dict] = []
    if not KB_DIR.exists():
        log.warning("knowledge_base dir not found: %s", KB_DIR)
        _chunks_cache = []
        return _chunks_cache
    for path in sorted(KB_DIR.rglob("*.txt")):
        folder = path.parent.name
        mode = _DIR_MODE.get(folder)
        if not mode:
            continue
        for file_title, section in _split_sections(path.read_text(encoding="utf-8")):
            text = f"[{file_title}]\n{section}" if file_title else section
            chunks.append({"mode": mode, "source": f"{folder}/{path.name}", "title": file_title, "text": text})
    _chunks_cache = chunks
    log.info("RAG: загружено %d чанков из базы знаний", len(chunks))
    return chunks


# ── keyword-фолбэк ──────────────────────────────────────────────────────────────

def _tokenize(s: str) -> list[str]:
    words = re.findall(r"[\w]+", s.lower())
    return [w for w in words if len(w) >= 3 and w not in _STOPWORDS]


def _keyword_search(mode: str, query: str, k: int) -> list[dict]:
    q_tokens = set(_tokenize(query))
    if not q_tokens:
        return []
    scored: list[tuple[float, dict]] = []
    for ch in load_chunks():
        if ch["mode"] != mode:
            continue
        text_tokens = _tokenize(ch["text"])
        if not text_tokens:
            continue
        hits = sum(1 for t in text_tokens if t in q_tokens)
        if hits:
            scored.append((hits / math.sqrt(len(text_tokens)), ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [ch for _, ch in scored[:k]]


# ── векторный поиск ──────────────────────────────────────────────────────────────

def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        # Эмбеддинги берём из OpenAI (даже если чат через OpenRouter).
        key = settings.openai_api_key or settings.openrouter_api_key
        if not key:
            raise RuntimeError("нет ключа для эмбеддингов (OPENAI_API_KEY)")
        base = "https://openrouter.ai/api/v1" if (not settings.openai_api_key and settings.openrouter_api_key) else None
        _client = AsyncOpenAI(api_key=key, base_url=base)
    return _client


async def embed(texts: list[str]) -> list[list[float]]:
    resp = await _get_client().embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def _load_index() -> list[dict] | None:
    global _index_cache
    if _index_cache is not None:
        return _index_cache or None
    if not INDEX_PATH.exists():
        _index_cache = []
        return None
    try:
        _index_cache = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        log.info("RAG: загружен векторный индекс (%d записей)", len(_index_cache))
    except (ValueError, OSError) as e:
        log.warning("RAG: не удалось прочитать индекс: %s", e)
        _index_cache = []
    return _index_cache or None


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


async def _vector_search(mode: str, query: str, k: int) -> list[dict]:
    index = _load_index()
    if not index:
        return []
    q_vec = (await embed([query]))[0]
    scored: list[tuple[float, dict]] = []
    for item in index:
        if item.get("mode") != mode:
            continue
        scored.append((_cosine(q_vec, item["embedding"]), item))
    scored.sort(key=lambda x: x[0], reverse=True)
    # отсекаем явно нерелевантное
    return [it for s, it in scored[:k] if s > 0.2]


# ── публичный API ────────────────────────────────────────────────────────────────

async def retrieve(mode: str, query: str, k: int = 3) -> str:
    """Топ-k фрагментов базы по запросу в рамках режима. Вектор → keyword-фолбэк."""
    results: list[dict] = []
    try:
        results = await _vector_search(mode, query, k)
    except Exception as e:  # noqa: BLE001 — эмбеддер недоступен → фолбэк
        log.warning("RAG vector search failed (%s) → keyword fallback", e)
    if not results:
        results = _keyword_search(mode, query, k)
    if not results:
        return ""
    parts, total = [], 0
    for ch in results:
        t = ch["text"]
        if total + len(t) > MAX_CONTEXT_CHARS:
            t = t[: MAX_CONTEXT_CHARS - total]
        parts.append(t)
        total += len(t)
        if total >= MAX_CONTEXT_CHARS:
            break
    return "\n\n---\n\n".join(parts)
