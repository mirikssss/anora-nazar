"""Таблицы модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from node.database import Base


class ModelVersion(Base):
    """Версия модели в реестре: типология, точки, контракт признаков, состояние выпуска."""

    __tablename__ = "model_versions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    typology: Mapped[str] = mapped_column(String(8))
    points: Mapped[list[str]] = mapped_column(JSONB)
    feature_set_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("status in ('shadow', 'active', 'retired')", name="status"),)
