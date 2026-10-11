"""Таблицы модуля."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from node.database import Base

_REALM_FK = "realms.id"


class ProcessedEvent(Base):
    """Идемпотентный потребитель: событие с виденным идентификатором отбрасывается."""

    __tablename__ = "processed_events"

    realm_id: Mapped[UUID] = mapped_column(ForeignKey(_REALM_FK, ondelete="CASCADE"), primary_key=True)
    event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    source: Mapped[str] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(16))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EntityVersion(Base):
    """Последняя применённая версия сущности внутри источника (кроме заявок: их версия — на строке заявки)."""

    __tablename__ = "entity_versions"

    realm_id: Mapped[UUID] = mapped_column(ForeignKey(_REALM_FK, ondelete="CASCADE"), primary_key=True)
    source: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    last_version: Mapped[int] = mapped_column(Integer)


class PendingEvent(Base):
    """Событие из будущего: ждёт пропущенную версию."""

    __tablename__ = "pending_events"

    realm_id: Mapped[UUID] = mapped_column(ForeignKey(_REALM_FK, ondelete="CASCADE"), primary_key=True)
    source: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    envelope: Mapped[dict[str, Any]] = mapped_column(JSONB)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SourceFact(Base):
    """Факт из источника банка (сессия, бюро и т. п.) с двумя временами."""

    __tablename__ = "source_facts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey(_REALM_FK, ondelete="CASCADE"), index=True)
    event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    source: Mapped[str] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(128))
    subject_key: Mapped[str | None] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Watermark(Base):
    """Отметка производителя событий: сколько ещё не доставлено и с какого времени."""

    __tablename__ = "watermarks"

    realm_id: Mapped[UUID] = mapped_column(ForeignKey(_REALM_FK, ondelete="CASCADE"), primary_key=True)
    producer: Mapped[str] = mapped_column(String(64), primary_key=True)
    pending_count: Mapped[int] = mapped_column(Integer)
    oldest_pending_occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MarkMetric(Base):
    """Метрики пометок: задержка «получили → пометили» и «сигнал пришёл уже после резерва»."""

    __tablename__ = "mark_metrics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey(_REALM_FK, ondelete="CASCADE"), index=True)
    trigger: Mapped[str] = mapped_column(String(160))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    marked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    marked_count: Mapped[int] = mapped_column(Integer)
    marked_after_reserve: Mapped[int] = mapped_column(Integer)
