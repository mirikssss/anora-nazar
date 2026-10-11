"""Таблицы модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Identity, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from network_operator.database import Base


class Watch(Base):
    """Подписка заявки ref кредитора на токен до срока; снимается по сроку."""

    __tablename__ = "watches"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    lender: Mapped[str] = mapped_column(String(16))
    realm_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    ref: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(16))
    key_version: Mapped[int] = mapped_column(Integer)
    token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    watch_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "lender",
            "realm_id",
            "ref",
            "kind",
            "key_version",
            "token",
            name="uq_watches_ref_token",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_watches_lookup", "kind", "key_version", "token"),
    )


class Notification(Base):
    """Уведомление кредитору о новом совпадении: одно на заявку ref и событие другого кредитора."""

    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    lender: Mapped[str] = mapped_column(String(16))
    realm_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    ref: Mapped[str] = mapped_column(String(128))
    event_root: Mapped[int] = mapped_column(BigInteger)
    kinds: Mapped[list[str]] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(512))

    __table_args__ = (
        UniqueConstraint(
            "lender",
            "realm_id",
            "ref",
            "event_root",
            name="uq_notifications_ref_event",
            postgresql_nulls_not_distinct=True,
        ),
        Index(
            "ix_notifications_due",
            "next_attempt_at",
            postgresql_where=text("delivered_at IS NULL AND failed_at IS NULL"),
        ),
    )
