"""Собирает векторный RAG-индекс из app/knowledge_base → app/rag_index.json.

Запуск (нужен OPENAI_API_KEY в .env):
    python -m scripts.build_index

Индекс кладётся рядом с кодом и попадает в Docker-образ. Пересобирать при
изменении базы знаний. Если индекса нет — RAG работает на keyword-фолбэке.
"""
import asyncio
import json

from app.services import rag


async def main() -> None:
    chunks = rag.load_chunks()
    if not chunks:
        print("База знаний пуста — нечего индексировать.")
        return
    print(f"Чанков: {len(chunks)}. Считаю эмбеддинги ({rag.EMBED_MODEL})…")
    vectors = await rag.embed([c["text"] for c in chunks])
    index = [
        {"mode": c["mode"], "source": c["source"], "title": c["title"], "text": c["text"], "embedding": v}
        for c, v in zip(chunks, vectors)
    ]
    rag.INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    by_mode: dict[str, int] = {}
    for c in chunks:
        by_mode[c["mode"]] = by_mode.get(c["mode"], 0) + 1
    print(f"✅ Индекс сохранён: {rag.INDEX_PATH}")
    print(f"   По режимам: {by_mode}")


if __name__ == "__main__":
    asyncio.run(main())
