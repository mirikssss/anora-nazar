"""Таблицы модуля."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bank_sim.database import Base


class Transfer(Base):
    """Перевод с карты после зачисления: решение ТАФ банка, рекомендация узла (Т3) и кто решил."""

    __tablename__ = "transfers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("sandboxes.id", ondelete="CASCADE"))
    application_id: Mapped[str] = mapped_column(String(32))
    pinfl: Mapped[str] = mapped_column(String(14))
    account: Mapped[str] = mapped_column(String(64))
    recipient_card: Mapped[str] = mapped_column(String(16))
    amount: Mapped[int] = mapped_column(BigInteger)
    recipient_is_new: Mapped[bool] = mapped_column(Boolean)
    balance_before_credit: Mapped[int] = mapped_column(BigInteger)
    credit_share: Mapped[float] = mapped_column(Float)
    credited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16))
    decided_by: Mapped[str] = mapped_column(String(16))
    recommendation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    node_error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    own_rule: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    resolution: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_transfers_realm_application", "realm_id", "application_id"),)
