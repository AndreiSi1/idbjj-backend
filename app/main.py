import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import admin, webhooks
from app.services import max_api, telegram_api

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="ID BJJ Bot Backend", version="0.1.0")

# Статика админки (Chart.js) и ассеты лендинга.
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(webhooks.router)
app.include_router(admin.router)

_LANDING = Path("app/landing/index.html")


@app.get("/", include_in_schema=False)
async def landing() -> HTMLResponse:
    """Лендинг с подстановкой ссылок на ботов из .env."""
    html = _LANDING.read_text(encoding="utf-8")
    html = html.replace("{{TELEGRAM_BOT_URL}}", settings.telegram_bot_url or "#")
    html = html.replace("{{MAX_BOT_URL}}", settings.max_bot_url or "#")
    return HTMLResponse(html)


@app.get("/terms", include_in_schema=False)
async def terms() -> FileResponse:
    return FileResponse("app/landing/legal/terms.html")


@app.get("/privacy", include_in_schema=False)
async def privacy() -> FileResponse:
    return FileResponse("app/landing/legal/privacy.html")


@app.on_event("startup")
async def register_webhooks() -> None:
    """Подписать MAX и Telegram на отправку апдейтов, если каждый сконфигурирован."""
    base = settings.public_base_url.rstrip("/") if settings.public_base_url else ""

    if settings.max_bot_token and base and settings.max_webhook_secret:
        url = f"{base}/webhooks/max/{settings.max_webhook_secret}"
        ok = await max_api.set_webhook(url)
        log.info("MAX webhook %s -> %s", url, "registered" if ok else "FAILED")
    else:
        log.info("MAX webhook not registered (token/public_base_url/secret missing)")

    if settings.telegram_bot_token and base and settings.telegram_webhook_secret:
        url = f"{base}/webhooks/telegram/{settings.telegram_webhook_secret}"
        ok = await telegram_api.set_webhook(url)
        log.info("Telegram webhook %s -> %s", url, "registered" if ok else "FAILED")
    else:
        log.info("Telegram webhook not registered (token/public_base_url/secret missing)")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
