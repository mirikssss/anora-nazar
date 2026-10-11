"""Таблицы модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Identity, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from network_operator.database import Base


class RequestLogEntry(Base):
    """Журнал запросов к оператору: кто, когда, сколько токенов и какие счётчики — без значений и токенов."""

    __tablename__ = "request_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    client: Mapped[str] = mapped_column(String(64))
    lender: Mapped[str | None] = mapped_column(String(16))
    realm_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    operation: Mapped[str] = mapped_column(String(16))
    items: Mapped[int] = mapped_column(Integer)
    tokens: Mapped[int] = mapped_column(Integer)
    counters: Mapped[list[str]] = mapped_column(JSONB)
    history: Mapped[bool] = mapped_column(Boolean)

    __table_args__ = (Index("ix_request_log_usage", "lender", "realm_id", "operation", "at"),)
