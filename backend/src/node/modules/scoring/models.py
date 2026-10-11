"""Таблицы модуля."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from node.database import Base


class ModelVersion(Base):
    """Неизменяемая версия модели: контракт признаков, артефакт LightGBM, калибровка, данные обучения, метрики."""

    __tablename__ = "model_versions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    typology: Mapped[str] = mapped_column(String(8))
    points: Mapped[list[str]] = mapped_column(JSONB)
    feature_set_version: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(16))  # lightgbm | logistic — формат артефакта
    feature_names: Mapped[list[str]] = mapped_column(JSONB)
    # артефакт — сотни килобайт: грузится только когда бустера ещё нет в кэше процесса
    artifact: Mapped[str] = mapped_column(Text, deferred=True)
    calibration: Mapped[dict[str, Any]] = mapped_column(JSONB)
    training: Mapped[dict[str, Any]] = mapped_column(JSONB)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB)
    realm_id: Mapped[UUID | None] = mapped_column(ForeignKey("realms.id", ondelete="CASCADE"))  # где обучена
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ModelRelease(Base):
    """Выпуск версии в контуре: запрос одного риск-менеджера и подтверждение другого (второй подписант).

    В песочнице выпуск действует только для её посетителя; общий мир выпускает команда стенда.
    """

    __tablename__ = "model_releases"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("realms.id", ondelete="CASCADE"))
    model_version_id: Mapped[UUID] = mapped_column(ForeignKey("model_versions.id", ondelete="CASCADE"))
    model_name: Mapped[str] = mapped_column(String(64))
    requested_by: Mapped[str] = mapped_column(String(64))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(64))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_model_releases_realm_name", "realm_id", "model_name", "approved_at"),)


class TrainingRun(Base):
    """Запуск обучения из контура: метки мира и песочницы → новые версии в тень → выпуск вторым подписантом."""

    __tablename__ = "training_runs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("realms.id", ondelete="CASCADE"), index=True)
    requested_by: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    versions: Mapped[list[str]] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (CheckConstraint("status in ('queued', 'running', 'done', 'failed')", name="status"),)
