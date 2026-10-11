"""Доступ к таблицам модуля."""

from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from node.modules.ingest.models import (
    EntityVersion,
    MarkMetric,
    PendingEvent,
    ProcessedEvent,
    SourceFact,
    Watermark,
)


def claim_event(session: Session, values: dict[str, Any]) -> bool:
    inserted = session.scalar(
        insert(ProcessedEvent).values(**values).on_conflict_do_nothing().returning(ProcessedEvent.event_id)
    )
    return inserted is not None


def set_outcome(session: Session, realm_id: UUID, event_id: UUID, outcome: str) -> None:
    event = session.get(ProcessedEvent, (realm_id, event_id))
    if event is not None:
        event.outcome = outcome


def entity_version_for_update(
    session: Session, realm_id: UUID, source: str, entity_type: str, entity_id: str
) -> EntityVersion | None:
    return session.scalars(
        select(EntityVersion)
        .where(
            EntityVersion.realm_id == realm_id,
            EntityVersion.source == source,
            EntityVersion.entity_type == entity_type,
            EntityVersion.entity_id == entity_id,
        )
        .with_for_update()
    ).one_or_none()


def save_entity_version(
    session: Session, realm_id: UUID, source: str, entity_type: str, entity_id: str, version: int
) -> None:
    stmt = insert(EntityVersion).values(
        realm_id=realm_id, source=source, entity_type=entity_type, entity_id=entity_id, last_version=version
    )
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=[
                EntityVersion.realm_id,
                EntityVersion.source,
                EntityVersion.entity_type,
                EntityVersion.entity_id,
            ],
            set_={"last_version": version},
        )
    )


def park(session: Session, values: dict[str, Any]) -> None:
    session.execute(insert(PendingEvent).values(**values).on_conflict_do_nothing())


def take_parked(
    session: Session, realm_id: UUID, source: str, entity_type: str, entity_id: str, version: int
) -> PendingEvent | None:
    parked = session.get(PendingEvent, (realm_id, source, entity_type, entity_id, version))
    if parked is not None:
        session.delete(parked)
    return parked


def drop_parked_up_to(session: Session, realm_id: UUID, entity_type: str, entity_id: str, version: int) -> None:
    session.execute(
        delete(PendingEvent).where(
            PendingEvent.realm_id == realm_id,
            PendingEvent.entity_type == entity_type,
            PendingEvent.entity_id == entity_id,
            PendingEvent.version <= version,
        )
    )


def add_fact(session: Session, values: dict[str, Any]) -> None:
    session.add(SourceFact(**values))


def upsert_watermark(session: Session, values: dict[str, Any]) -> None:
    stmt = insert(Watermark).values(**values)
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=[Watermark.realm_id, Watermark.producer],
            set_={
                "pending_count": stmt.excluded.pending_count,
                "oldest_pending_occurred_at": stmt.excluded.oldest_pending_occurred_at,
                "reported_at": stmt.excluded.reported_at,
            },
            where=Watermark.reported_at <= stmt.excluded.reported_at,
        )
    )


def watermarks(session: Session, realm_id: UUID, producers: list[str]) -> dict[str, Watermark]:
    rows = session.scalars(select(Watermark).where(Watermark.realm_id == realm_id, Watermark.producer.in_(producers)))
    return {w.producer: w for w in rows}


def add_metric(session: Session, values: dict[str, Any]) -> None:
    session.add(MarkMetric(**values))


def metric_summary(session: Session, realm_id: UUID) -> dict[str, Any]:
    latency_ms = func.extract("epoch", MarkMetric.marked_at - MarkMetric.received_at) * 1000
    row = session.execute(
        select(
            func.count(),
            func.coalesce(func.sum(MarkMetric.marked_count), 0),
            func.coalesce(func.sum(MarkMetric.marked_after_reserve), 0),
            func.percentile_cont(0.95).within_group(latency_ms),
            func.max(latency_ms),
        ).where(MarkMetric.realm_id == realm_id)
    ).one()
    return {
        "triggers": row[0],
        "marked": int(row[1]),
        "marked_after_reserve": int(row[2]),
        "mark_latency_p95_ms": None if row[3] is None else round(float(row[3]), 3),
        "mark_latency_max_ms": None if row[4] is None else round(float(row[4]), 3),
    }
