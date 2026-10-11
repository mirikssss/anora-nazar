"""Таблицы модуля."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from node.database import Base

ACTIVE = "active"
CANCELLED = "cancelled"


class Application(Base):
    """Строка заявки — точка порядка: её блокируют и резерв разрешения, и пометка «нужна новая оценка»."""

    __tablename__ = "applications"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("realms.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(128))
    channel: Mapped[str] = mapped_column(String(16))
    subject_key: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16))
    current_version: Mapped[int] = mapped_column(Integer)
    assessed_version: Mapped[int | None] = mapped_column(Integer)
    latest_decision_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    # Итог последней оценки — на самой строке, которую блокирует резерв: проверка без лишних чтений.
    assessment_point: Mapped[str | None] = mapped_column(String(4))
    assessment_outcome: Mapped[str | None] = mapped_column(String(16))
    assessment_level: Mapped[str | None] = mapped_column(String(8))
    assessment_valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    needs_reassessment: Mapped[bool] = mapped_column(Boolean)
    reassessment_cause: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    version_gap_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("realm_id", "external_id", name="uq_applications_realm_external"),
        CheckConstraint(f"status in ('{ACTIVE}', '{CANCELLED}')", name="status"),
        CheckConstraint("channel in ('online', 'program')", name="channel"),
    )


class ApplicationVersion(Base):
    """Неизменяемый снимок версии заявки, как его прислал владелец — конвейер."""

    __tablename__ = "application_versions"

    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
