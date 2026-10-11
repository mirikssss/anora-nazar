"""Таблицы модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from node.database import Base

WORLD = "world"
SANDBOX = "sandbox"


class Realm(Base):
    __tablename__ = "realms"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"kind in ('{WORLD}', '{SANDBOX}')", name="kind"),
        Index("uq_realms_single_world", "kind", unique=True, postgresql_where=text(f"kind = '{WORLD}'")),
    )
