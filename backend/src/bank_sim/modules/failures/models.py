"""Таблицы модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, false
from sqlalchemy.orm import Mapped, mapped_column

from bank_sim.database import Base


class FailureFlags(Base):
    """Включённые сбои песочницы: каждый посетитель ломает только своё демо."""

    __tablename__ = "failure_flags"

    realm_id: Mapped[UUID] = mapped_column(ForeignKey("sandboxes.id", ondelete="CASCADE"), primary_key=True)
    lose_outcome: Mapped[bool] = mapped_column(Boolean)
    node_unavailable: Mapped[bool] = mapped_column(Boolean)
    queue_lag: Mapped[bool] = mapped_column(Boolean)
    network_unavailable: Mapped[bool] = mapped_column(Boolean, server_default=false())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
