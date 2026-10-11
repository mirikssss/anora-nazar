"""Таблицы модуля."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from node.database import Base


class NetworkToken(Base):
    """Кеш токенов OPRF. Значение идентификатора хранится только ключом HMAC узла — как в индексе связей.

    Ротация ключа у оператора (новая версия) — кеш очищается, токены получаются заново.
    """

    __tablename__ = "network_tokens"

    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    value_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    key_version: Mapped[int] = mapped_column(Integer)
    token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class NetworkNotification(Base):
    """Уведомление оператора о новом совпадении: одно на notification_id, повтор доставки — без второй пометки."""

    __tablename__ = "network_notifications"

    notification_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("realms.id", ondelete="CASCADE"), index=True)
    application_id: Mapped[UUID | None] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    kinds: Mapped[list[str]] = mapped_column(JSONB)
    outcome: Mapped[str] = mapped_column(String(16))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class NetworkObservationRow(Base):
    """Ответ сети на прошлый момент для обучения и проверки point-in-time (право history у оператора)."""

    __tablename__ = "network_observations"

    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), primary_key=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    contract: Mapped[str] = mapped_column(String(32))
    observation: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
