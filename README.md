# ID BJJ Bot — backend (уход от Salebot на свой VPS)

Самостоятельный бот для **MAX и Telegram**: принимает апдейты вебхуком и сам
отвечает через Bot API каждого мессенджера. Salebot больше не нужен. Стек повторяет
проект «Спецы Ру»: **FastAPI + PostgreSQL + Caddy (TLS) в Docker**, плюс 3 AI-ассистента
на ChatGPT/OpenRouter.

**Один сценарий — два канала.** Ядро (`dialog.py`) не знает, где работает; отправка
идёт через `messenger`, который диспетчеризует в MAX или Telegram. Реактивный диалог
идентичен в обоих каналах (проверено smoke-тестом). Проактивные рассылки —
**только Telegram** (в MAX запрещены правилами платформы), это зашито в `broadcast.py`.

## Архитектура

```
Пользователь (MAX / Telegram)
      │  webhook /webhooks/max/<secret>  |  /webhooks/telegram/<secret>
      ▼
Caddy (TLS, домен) ─► FastAPI ─► dialog.py (FSM) ─► messenger ─► MAX / Telegram Bot API
                          │                                       (+ OpenAI/OpenRouter)
                          ▼
                      PostgreSQL
```

| Слой | Файл |
|---|---|
| Приём апдейтов (MAX + Telegram) | `app/routers/webhooks.py` |
| Транспорт MAX | `app/services/max_api.py` |
| Транспорт Telegram | `app/services/telegram_api.py` |
| Диспетчер по каналу | `app/services/messenger.py` |
| Проактивные рассылки (только Telegram) | `app/services/broadcast.py` |
| Сценарий-FSM (замена воронки Salebot) | `app/services/dialog.py` |
| 3 AI-ассистента (LLM + промпты + RAG) | `app/services/ai.py` |
| Прогресс (пояс + XP/уровни) | `app/services/progress.py` |
| Админ-панель (дашборд, лиды, рассылки, переписка) | `app/routers/admin.py` |
| Метрики дашборда | `app/services/metrics.py` |
| Лендинг (`/`), юр-страницы (`/terms`,`/privacy`) | `app/landing/` |
| Состояние / профиль / прогресс / лиды | `app/db/models.py` |

Идентичность пользователя — пара `(channel, ext_id)`; состояние диалога привязано к
внутреннему `user_id`, поэтому одинаково для любого канала. `DialogState.mode`
(trainer/encyclopedia/dietolog) заменяет метки Salebot: когда режим активен, текст
пользователя уходит в нужного AI-ассистента.

## 6 модулей (как в Salebot-версии)

1. 🥋 Онлайн-тренер — анкета (5 шагов) → AI Тренер с профилем
2. 🏆 Подготовка к соревнованиям — Gi/No-Gi/ОФП/Ментал/Полный план
3. 📚 Энциклопедия BJJ — AI Энциклопедия
4. 🥗 Диета — анкета (6 шагов) → AI Диетолог (Миффлин-Сан Жеор)
5. 🎬 ID BJJ+ — анонс платформы
6. ✉️ Связаться с тренером — тип заявки + телефон → таблица `leads`

## Локальный запуск

```bash
cp .env.example .env          # заполните MAX_BOT_TOKEN, OPENAI_API_KEY и пр.
docker compose -f docker-compose.prod.yml up -d --build
```

Health-check: `GET /health`. Миграции применяются автоматически при старте.

## Деплой на VPS

1. Купить домен, направить A-запись на IP VPS.
2. В `Caddyfile` заменить `idbjj.example.ru` на ваш домен.
3. В `.env`: `PUBLIC_BASE_URL=https://<домен>`; по каналам:
   - MAX: `MAX_BOT_TOKEN` от @MasterBot, `MAX_WEBHOOK_SECRET=$(openssl rand -hex 32)`;
   - Telegram: `TELEGRAM_BOT_TOKEN` от @BotFather, `TELEGRAM_WEBHOOK_SECRET=$(openssl rand -hex 32)`.
   Можно включить любой один или оба — вебхуки регистрируются для тех, чьи токены заданы.
4. `docker compose -f docker-compose.prod.yml up -d --build` — Caddy сам получит TLS,
   бэкенд на старте зарегистрирует вебхуки.

> ⚠️ Бота в MAX могут создавать только юрлица/ИП; рассылки по таймеру в MAX запрещены.
> Telegram-бот заводится за 5 минут без юрлица — удобно начать с него, MAX подключить позже.

## AI: ChatGPT или OpenRouter

В `.env`: `LLM_PROVIDER=openai` (ключ `OPENAI_API_KEY`, модель `OPENAI_MODEL`) либо
`LLM_PROVIDER=openrouter` (`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`,
`OPENROUTER_FALLBACKS`). Один OpenAI-совместимый клиент на оба варианта.

Системные промпты — `app/prompts/{trainer,encyclopedia,dietolog}.txt`
(скопированы из `03_AI_Prompty`). Плейсхолдеры `#{Пояс}` и т.п. подставляются
из анкет (`Profile.trainer` / `Profile.diet`).

## RAG (база знаний)

База знаний лежит в `app/knowledge_base/` (18 .txt, разложены по режимам). RAG —
`app/services/rag.py`: чанкинг по markdown-секциям (145 чанков), поиск двухрежимный:

- **векторный** — если собран `app/rag_index.json` (эмбеддинги OpenAI
  `text-embedding-3-small`), косинус по top-k в рамках режима;
- **keyword-фолбэк** — работает офлайн без индекса/ключа.

Собрать векторный индекс (нужен `OPENAI_API_KEY`):
```bash
python -m scripts.build_index   # → app/rag_index.json
```
Пересобирать при изменении базы знаний. Папки → режимы: `01_entsiklopediya`→
encyclopedia, `02_podgotovka`+`04_online_trener`→trainer, `03_dieta`→dietolog.

## Каналы и рассылки

- **Telegram** включается заполнением `TELEGRAM_BOT_TOKEN` + `TELEGRAM_WEBHOOK_SECRET`
  (вебхук регистрируется на старте). Сценарий тот же, что в MAX.
- **Проактивные рассылки** — `broadcast.broadcast(session, text)` / `send_proactive(...)`:
  идут только в Telegram (для MAX молча пропускаются). Вызов — из планировщика (cron).
  Реакция на событие (уведомление тренеру) рассылкой не считается и работает везде.

## Прогресс ученика

Кнопка «📈 Мой прогресс» показывает **реальный ранг** (пояс из анкеты тренера + полоски)
и **активность** (XP/уровни за действия в боте). XP: согласие +5, анкеты +20, вопрос
ассистенту +2, заявка +10 (`app/services/progress.py`). Распределение поясов — в админке.

## Админ-панель и лендинг

- **Панель** `/admin` (HTTP Basic, `ADMIN_USER`/`ADMIN_PASSWORD`): дашборд (KPI, рост,
  пояса), лиды, рассылки (Telegram), переписка с ответом в канал пользователя.
- **Лендинг** `/` — чёрно-белый, контент idbjj.ru (Симферополь, цены, контакты);
  ссылки на ботов берутся из `TELEGRAM_BOT_URL`/`MAX_BOT_URL`.

## Готово

- [x] **Мультиканальность**: один сценарий в MAX и Telegram (идентично, smoke-тест зелёный).
- [x] **RAG** по базе знаний (вектор + keyword-фолбэк) — `app/services/rag.py`.
- [x] **Прогресс**: пояс + XP/уровни, кнопка «Мой прогресс» — `app/services/progress.py`.
- [x] **Админ-панель** + **лендинг** + юр-страницы `/terms`, `/privacy`.
- [x] **Уведомление тренеру** о новом лиде — `TRAINER_CHANNEL`/`TRAINER_CHAT_ID`.
- [x] **Защита рассылок**: проактив в MAX заблокирован на уровне кода.
- [x] **Деплой**: см. `DEPLOY.md` (runbook по VPS).

## TODO (следующие шаги)

- [ ] Планировщик (cron) для `broadcast` — напоминания/анонсы по таймеру в Telegram.
- [ ] Материалы модуля «Подготовка к соревнованиям» (сейчас тексты-заглушки в меню;
      AI-материалы уже доступны через RAG режима trainer).
- [ ] Заполнить реквизиты `[●]` в `app/landing/legal/*.html` и согласовать с юристом.
- [ ] Полоски (stripes) к поясу — сейчас 0 по умолчанию (можно добавить в анкету/админку).
- [ ] Тесты (pytest) — есть `smoke_test.py` и `progress_test.py`.
```
