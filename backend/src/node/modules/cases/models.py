"""Таблицы модуля."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from node.database import Base


class Case(Base):
    """Дело: очередь, зона, стратегия группы, срок, исполнитель, исход. Решения — по каждой заявке отдельно."""

    __tablename__ = "cases"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("realms.id", ondelete="CASCADE"), index=True)
    queue: Mapped[str] = mapped_column(String(16))
    zone: Mapped[int] = mapped_column(Integer)
    strategy: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    assignee: Mapped[str | None] = mapped_column(String(64))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(32))
    checklist: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("status in ('open', 'in_progress', 'escalated', 'closed')", name="status"),
        CheckConstraint("strategy in ('application', 'identity', 'coordination')", name="strategy"),
        Index("ix_cases_realm_queue_status", "realm_id", "queue", "status"),
    )


class CaseApplication(Base):
    """Заявка в деле: сводка решения на момент включения (уровень, причины, оценочная стоимость риска) и решение
    по участнику — удержание, отпуск или отказ — с ролью и основанием."""

    __tablename__ = "case_applications"

    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(128))
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB)
    decision: Mapped[str | None] = mapped_column(String(16))
    role: Mapped[str | None] = mapped_column(String(32))
    basis: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[str | None] = mapped_column(String(64))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_case_applications_application", "application_id"),)


class CaseEvent(Base):
    """Лента дела: кто, когда, что и почему. Та же запись уходит в журнал — её номер в цепочке контура здесь."""

    __tablename__ = "case_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    actor: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(48))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    audit_seq: Mapped[int] = mapped_column(BigInteger)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
