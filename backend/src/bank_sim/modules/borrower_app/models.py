"""Таблицы модуля."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bank_sim.database import Base


class BorrowerApplication(Base):
    """Онлайн-заявка, поданная из приложения заёмщика, и действия клиента в приложении."""

    __tablename__ = "borrower_applications"

    realm_id: Mapped[UUID] = mapped_column(ForeignKey("sandboxes.id", ondelete="CASCADE"), primary_key=True)
    application_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    persona_code: Mapped[str | None] = mapped_column(String(32))  # None — заявку подал сценарий
    intent_answers: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    intent_answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pressure_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
