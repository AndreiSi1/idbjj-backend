# Деплой ID BJJ Bot на VPS

Пошаговый runbook. Стек: Docker Compose (Postgres + FastAPI + Caddy с авто-TLS).
Каналы MAX и Telegram — можно включить любой один или оба.

## 0. Что подготовить заранее

- **VPS** с Ubuntu/Debian, публичным IP, открытыми портами 80 и 443. **РФ-хостинг**
  (152-ФЗ требует хранить ПДн в России — Postgres стоит на этом же VPS).
- **Домен** (напр. `bot.idbjj.ru`), A-запись → IP VPS.
- **Токен бота**:
  - Telegram — у @BotFather (5 минут, без юрлица);
  - MAX — у @MasterBot (⚠️ нужен ИП/ЮЛ и верификация).
- **Ключ LLM**: `OPENAI_API_KEY` (или OpenRouter) — из проектов tg-marketing / sidorenko-sales.

## 1. Установить Docker на VPS

```bash
curl -fsSL https://get.docker.com | sh
```

## 2. Залить код

Скопировать папку `backend/` на сервер (scp/rsync/git). Дальше работаем в ней.

## 3. Настроить домен в Caddy

В `Caddyfile` заменить `idbjj.example.ru` на ваш домен:
```
bot.idbjj.ru {
    reverse_proxy api:8000
    ...
}
```

## 4. Заполнить .env

```bash
cp .env.example .env
nano .env
```
Минимум для старта (пример с Telegram):
```
PUBLIC_BASE_URL=https://bot.idbjj.ru
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_WEBHOOK_SECRET=<openssl rand -hex 32>
TELEGRAM_BOT_URL=https://t.me/ваш_бот
OPENAI_API_KEY=sk-...
ADMIN_PASSWORD=<длинный пароль для панели>
TRAINER_CHANNEL=telegram
TRAINER_CHAT_ID=<ваш telegram id>
```
MAX добавляется аналогично (`MAX_BOT_TOKEN`, `MAX_WEBHOOK_SECRET`).
Сгенерировать секрет: `openssl rand -hex 32`.

## 5. Запустить

```bash
docker compose -f docker-compose.prod.yml up -d --build
```
Что произойдёт автоматически:
- Postgres поднимется, миграции применятся (`alembic upgrade head`);
- Caddy получит TLS-сертификат Let's Encrypt для домена;
- бэкенд зарегистрирует вебхуки в Telegram и/или MAX.

Проверка: `curl https://bot.idbjj.ru/health` → `{"status":"ok"}`.

## 6. Собрать RAG-индекс (опционально, для семантического поиска)

```bash
docker compose -f docker-compose.prod.yml exec api python -m scripts.build_index
docker compose -f docker-compose.prod.yml restart api
```
Без индекса RAG работает на keyword-фолбэке (отвечает по базе знаний, но менее точно).

## 7. Проверить

- Напишите боту `/start` → согласие → меню (7 кнопок).
- Пройдите анкету тренера, задайте вопрос, посмотрите «📈 Мой прогресс».
- Откройте панель: `https://bot.idbjj.ru/admin` (логин/пароль из `.env`).
- Лендинг: `https://bot.idbjj.ru/`.

## 8. Узнать telegram id тренера

Напишите боту от имени тренера — id появится в логах:
```bash
docker compose -f docker-compose.prod.yml logs -f api | grep "telegram update"
```
Впишите его в `TRAINER_CHAT_ID`, перезапустите `api`.

## Вариант Б — co-host на существующем VPS (nginx-proxy)

Если разворачиваем РЯДОМ с другими сервисами на VPS, где уже работает
`nginx-proxy` + `acme-companion` (напр. 217.26.25.228), используем
`docker-compose.cohost.yml` — без своего Caddy, встраиваемся в общий прокси.

1. DNS: A-запись `bot.idbjj.ru` → IP VPS (cert выдаётся только после этого).
2. В `.env` задать `BOT_DOMAIN=bot.idbjj.ru`, `LETSENCRYPT_EMAIL=...`,
   `PUBLIC_BASE_URL=https://bot.idbjj.ru` (+ токены/ключи).
3. Залить `backend/` в отдельную папку (напр. `/home/app/idbjj/`).
4. Запуск (проект изолируется именем `idbjj`):
   ```bash
   docker compose -f docker-compose.cohost.yml up -d --build
   ```
   nginx-proxy сам подхватит `VIRTUAL_HOST`, acme-companion выпустит TLS.
5. Проверка: `curl https://bot.idbjj.ru/health`.

Изоляция: контейнеры `idbjj-*`, своя сеть `idbjj_internal`, свой том
`idbjj_pg_data` — не пересекается с другими стеками. Переезд на отдельный
сервер позже: `pg_dump` → копировать папку+дамп → `up` → переключить DNS.

## Обслуживание

```bash
docker compose -f docker-compose.prod.yml logs -f api      # логи
docker compose -f docker-compose.prod.yml restart api      # рестарт после правки .env
docker compose -f docker-compose.prod.yml down             # остановить
docker compose -f docker-compose.prod.yml exec postgres pg_dump -U idbjj idbjj > backup.sql   # бэкап БД
```

## Заметки

- Юр-документы `/terms` и `/privacy` — шаблоны: заполните реквизиты `[●]`
  (ИП, ИНН, e-mail) в `app/landing/legal/*.html` до публичного запуска.
- Рассылки (`/admin` → Рассылка) идут только в Telegram — в MAX запрещены правилами.
- Бэкап Postgres настройте на cron (том `pg_data` переживает пересборку контейнеров).
```
