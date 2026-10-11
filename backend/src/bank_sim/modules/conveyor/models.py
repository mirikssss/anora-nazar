"""Таблицы модуля."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from bank_sim.database import Base


class ConveyorApplication(Base):
    """Заявка у конвейера — владельца оригинала. Узел хранит только снимки её версий."""

    __tablename__ = "applications"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("sandboxes.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(32))
    channel: Mapped[str] = mapped_column(String(16))
    version: Mapped[int] = mapped_column(Integer)
    draft: Mapped[dict[str, Any]] = mapped_column(JSONB)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32))
    last_decision: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    node_state: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("realm_id", "external_id", name="uq_applications_realm_external"),)
