"""Доступ к таблицам модуля."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, insert, select, text
from sqlalchemy.orm import Session

from node.modules.audit.models import AuditCheckpoint, AuditRecord


def lock_chain(session: Session, realm_id: UUID) -> None:
    """Один писатель на цепочку контура: блокировка до конца транзакции."""
    key = int.from_bytes(realm_id.bytes[:8], "big", signed=True)
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def head(session: Session, realm_id: UUID) -> tuple[int, str] | None:
    row = session.execute(
        select(AuditRecord.seq, AuditRecord.hash)
        .where(AuditRecord.realm_id == realm_id)
        .order_by(AuditRecord.seq.desc())
        .limit(1)
    ).one_or_none()
    return None if row is None else (row.seq, row.hash)


def insert_record(session: Session, values: dict[str, Any]) -> None:
    session.execute(insert(AuditRecord).values(**values))


def records(session: Session, realm_id: UUID, after_seq: int = 0, limit: int | None = None) -> list[AuditRecord]:
    stmt = (
        select(AuditRecord)
        .where(AuditRecord.realm_id == realm_id, AuditRecord.seq > after_seq)
        .order_by(AuditRecord.seq)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt))


def last_checkpoint(session: Session, realm_id: UUID) -> AuditCheckpoint | None:
    return session.scalars(
        select(AuditCheckpoint)
        .where(AuditCheckpoint.realm_id == realm_id)
        .order_by(AuditCheckpoint.seq.desc())
        .limit(1)
    ).one_or_none()


def add_checkpoint(session: Session, checkpoint: AuditCheckpoint) -> None:
    session.add(checkpoint)


def unanchored(session: Session) -> list[AuditCheckpoint]:
    return list(
        session.scalars(
            select(AuditCheckpoint).where(AuditCheckpoint.anchored_at.is_(None)).order_by(AuditCheckpoint.created_at)
        )
    )


def checkpoints(session: Session, realm_id: UUID) -> list[AuditCheckpoint]:
    return list(
        session.scalars(
            select(AuditCheckpoint).where(AuditCheckpoint.realm_id == realm_id).order_by(AuditCheckpoint.seq)
        )
    )


def realms_needing_checkpoint(session: Session, created_before: datetime) -> list[UUID]:
    """Контуры, где после последней контрольной точки появились записи, а точка старше интервала."""
    last_cp = (
        select(
            AuditCheckpoint.realm_id,
            func.max(AuditCheckpoint.seq).label("seq"),
            func.max(AuditCheckpoint.created_at).label("created_at"),
        )
        .group_by(AuditCheckpoint.realm_id)
        .subquery()
    )
    heads = (
        select(AuditRecord.realm_id, func.max(AuditRecord.seq).label("seq")).group_by(AuditRecord.realm_id).subquery()
    )
    rows = session.execute(
        select(heads.c.realm_id)
        .outerjoin(last_cp, last_cp.c.realm_id == heads.c.realm_id)
        .where((last_cp.c.seq.is_(None)) | ((heads.c.seq > last_cp.c.seq) & (last_cp.c.created_at < created_before)))
    )
    return list(rows.scalars())


def checkpoint(session: Session, realm_id: UUID, seq: int) -> AuditCheckpoint | None:
    return session.get(AuditCheckpoint, (realm_id, seq))
