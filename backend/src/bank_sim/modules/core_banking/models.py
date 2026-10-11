"""Таблицы модуля."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bank_sim.database import Base

# Контракт единственной проводки с узлом (ревью B): по бизнес-операции «заявка + тип + транш» не больше одной
# незавершённой или исполненной попытки; повтор после сбоя идёт с тем же ключом операции.
LIVE_STATUSES = "status in ('in_progress', 'waiting_node', 'executed')"


class Operation(Base):
    """Операция АБС: зачисление или оплата поставщику. Ключ операции — он же ключ запроса разрешения."""

    __tablename__ = "operations"

    operation_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("sandboxes.id", ondelete="CASCADE"), index=True)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    application_external_id: Mapped[str] = mapped_column(String(32))
    application_version: Mapped[int] = mapped_column(Integer)
    operation_type: Mapped[str] = mapped_column(String(32))
    tranche: Mapped[int] = mapped_column(Integer)
    amount: Mapped[int] = mapped_column(BigInteger)
    account: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    acceptance_act_id: Mapped[str | None] = mapped_column(String(32))  # Т5: оплата поставщику — по акту приёмки
    permit: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    refusal: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    outcome_reported: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_operations_business_operation",
            "realm_id",
            "application_id",
            "operation_type",
            "tranche",
            unique=True,
            postgresql_where=text(LIVE_STATUSES),
        ),
    )
