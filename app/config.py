from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://idbjj:idbjj@localhost:5432/idbjj"

    # MAX Bot API
    max_bot_token: str = ""
    max_channel_id: str = ""
    max_webhook_secret: str = ""
    max_api_base: str = "https://botapi.max.ru"
    public_base_url: str = ""  # напр. https://idbjj.example.ru — для регистрации вебхука

    # Telegram Bot API (второй канал; тот же сценарий + проактивные рассылки)
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""  # X-Telegram-Bot-Api-Secret-Token
    telegram_api_base: str = "https://api.telegram.org"

    # Тренер (Петров Денис Иванович) — куда слать заявки из «Связаться с тренером».
    # trainer_channel: "max" или "telegram"; trainer_chat_id — id в этом канале.
    # Если id пуст — уведомления молча пропускаются, основной поток не ломается.
    trainer_channel: str = "max"
    trainer_chat_id: str = ""

    # Админ-панель (HTTP Basic). Если admin_password пуст — панель отдаёт 503.
    admin_user: str = "admin"
    admin_password: str = ""

    # Ссылки на ботов для лендинга (кнопки «Открыть в MAX / Telegram»).
    max_bot_url: str = ""
    telegram_bot_url: str = ""

    # LLM: основной провайдер — "openai" | "openrouter" | "gigachat".
    # Остальные с заданными кредами подключаются как авто-фоллбэк (надёжность).
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_fallbacks: str = ""  # "model-a,model-b" — резерв при 429/5xx

    # GigaChat (Сбер) — оплата рублями, freemium 1M токенов/мес. Авто-фоллбэк к OpenAI.
    gigachat_auth_key: str = ""             # Basic-ключ (client_id:client_secret в base64)
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_model: str = "GigaChat"        # GigaChat | GigaChat-Pro | GigaChat-Max

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    def model_post_init(self, __context) -> None:
        # Нормализуем DSN под asyncpg (на случай postgres:// от managed-хостинга).
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        if "?" in url:
            base, _, query = url.partition("?")
            params = [p for p in query.split("&") if not p.startswith("sslmode=")]
            url = base + ("?" + "&".join(params) if params else "")
        self.database_url = url


settings = Settings()
