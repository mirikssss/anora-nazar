"""Таблицы модуля."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from node.database import Base


class Decision(Base):
    """Запись решения. После создания не меняется: UPDATE запрещён триггером в базе."""

    __tablename__ = "decisions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("realms.id", ondelete="CASCADE"), index=True)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    point: Mapped[str] = mapped_column(String(4))
    application_version: Mapped[int] = mapped_column(Integer)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str] = mapped_column(String(16))
    level: Mapped[str | None] = mapped_column(String(8))
    action: Mapped[str] = mapped_column(String(32))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    record: Mapped[dict[str, Any]] = mapped_column(JSONB)
    record_hash: Mapped[str] = mapped_column(String(64))
