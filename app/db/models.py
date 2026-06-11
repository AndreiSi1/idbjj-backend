from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# JSONB на PostgreSQL, обычный JSON на sqlite (чтобы тесты гонялись на aiosqlite).
JSONType = JSONB().with_variant(JSON(), "sqlite")

CHANNELS = ("max", "telegram")


class User(Base):
    """Пользователь в одном из каналов. Идентичность — пара (channel, ext_id):
    id-пространства MAX и Telegram независимы, поэтому ключ составной.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[str] = mapped_column(String(16), default="max", index=True)
    ext_id: Mapped[str] = mapped_column(String(64), index=True)  # id пользователя в его канале
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    lang: Mapped[str | None] = mapped_column(String(8), nullable=True)  # ru|en|es|pt; NULL = ещё не выбран
    # Источник привлечения из deep-link (?start=yt|vk|reels…). NULL = прямой/неизвестно. First-touch.
    source: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # Кто пригласил (реферал): id пригласившего юзера. First-touch, ставится при создании.
    referred_by: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # Когда пользователь принял оферту и согласие на обработку ПДн (152-ФЗ). NULL = ещё не принял.
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("channel", "ext_id", name="uq_user_channel_ext"),
        CheckConstraint("channel in ('max','telegram')", name="ck_user_channel"),
    )


class DialogState(Base):
    """Состояние диалога — замена визуальной воронки Salebot. Привязано к внутреннему
    user_id, поэтому одинаково работает для любого канала.

    step — текущий узел FSM (см. app.services.dialog).
    mode — активный AI-ассистент: trainer | encyclopedia | dietolog | None.
           Заменяет метки Salebot (mode_trainer / mode_encyclopedia / mode_dietolog).
    data — накопленные поля анкеты до завершения шага.
    """

    __tablename__ = "dialog_state"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    step: Mapped[str] = mapped_column(String(48), default="menu")
    mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    data: Mapped[dict] = mapped_column(JSONType, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Profile(Base):
    """Профиль ученика для подстановки в системные промпты AI.

    Заполняется анкетами Тренера и Диеты. Поля хранятся в JSON, чтобы свободно
    добавлять/менять состав анкет без миграций (trainer_* и diet_* ключи).
    """

    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    trainer: Mapped[dict] = mapped_column(JSONType, default=dict)  # Пояс, Стаж, Частота, Цель, Травмы
    diet: Mapped[dict] = mapped_column(JSONType, default=dict)     # Пол, Возраст, Рост, Вес, Активность, Цель_диеты
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Progress(Base):
    """Уровень прогресса ученика: реальный BJJ-ранг (пояс + полоски) и активность в боте (XP).

    belt/stripes — ранг в зале (belt берётся из анкеты тренера). xp копится за действия
    в боте (см. app.services.progress), level вычисляется из xp на лету.
    """

    __tablename__ = "progress"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    belt: Mapped[str | None] = mapped_column(String(16), nullable=True)  # white/blue/purple/brown/black
    stripes: Mapped[int] = mapped_column(Integer, default=0)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Lead(Base):
    """Заявка из модуля «Связаться с тренером» (короткая воронка: тип + телефон)."""

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # тип заявки (пробное / вопрос / ...)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JournalEntry(Base):
    """Запись дневника тренировок: что отрабатывал ученик. Закрывает боль «забыл,
    что проходили», даёт повод возвращаться после каждой тренировки (ретеншн) и
    кормит AI-тренера историей для разбора и построения игры."""

    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class Message(Base):
    """Лог переписки: каждое входящее и исходящее сообщение (для истории и админки)."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    direction: Mapped[str] = mapped_column(String(8))  # 'in' | 'out'
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    __table_args__ = (
        CheckConstraint("direction in ('in','out')", name="ck_message_direction"),
    )
