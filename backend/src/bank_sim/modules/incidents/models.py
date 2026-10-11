"""Таблицы модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bank_sim.database import Base


class Incident(Base):
    """Жалоба клиента, документ органа или вывод внутреннего контроля по заявкам — источник меток узла."""

    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("sandboxes.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    typology: Mapped[str] = mapped_column(String(8))
    result: Mapped[str] = mapped_column(String(32))
    application_ids: Mapped[list[str]] = mapped_column(JSONB)
    case_key: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
