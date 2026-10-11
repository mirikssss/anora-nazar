"""Таблицы модуля."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from node.database import Base

RESERVED = "reserved"
EXECUTED = "executed"
NOT_EXECUTED = "not_executed"
UNKNOWN = "unknown"
BLOCKING_STATUSES = (RESERVED, UNKNOWN, EXECUTED)


class Permit(Base):
    """Разрешение на одну операцию. Уникальность «заявка + тип + транш» держит база (заметка 4 «Ядро»)."""

    __tablename__ = "permits"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("realms.id", ondelete="CASCADE"))
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    operation_type: Mapped[str] = mapped_column(String(32))
    tranche: Mapped[int] = mapped_column(Integer)
    operation_key: Mapped[str] = mapped_column(String(128))
    application_version: Mapped[int] = mapped_column(Integer)
    decision_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    amount: Mapped[int] = mapped_column(BigInteger)
    account: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    signature: Mapped[str] = mapped_column(String(128))
    key_id: Mapped[str] = mapped_column(String(32))
    reserved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"status in ('{RESERVED}', '{EXECUTED}', '{NOT_EXECUTED}', '{UNKNOWN}')", name="status"),
        UniqueConstraint("realm_id", "operation_key", name="uq_permits_realm_operation_key"),
        Index(
            "uq_permits_one_live_operation",
            "application_id",
            "operation_type",
            "tranche",
            unique=True,
            postgresql_where=text(f"status in ('{RESERVED}', '{UNKNOWN}', '{EXECUTED}')"),
        ),
        Index("ix_permits_status_expires", "status", "expires_at"),
    )


class Hold(Base):
    """Удержание на конкретную заявку со своим основанием; снимает его только итог проверки."""

    __tablename__ = "holds"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("realms.id", ondelete="CASCADE"))
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    decision_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    required_check: Mapped[str] = mapped_column(String(64))
    basis: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_by: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (CheckConstraint("status in ('active', 'released')", name="status"),)
