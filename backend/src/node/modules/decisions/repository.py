"""Доступ к таблицам модуля."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from node.modules.decisions.models import Decision


def add(session: Session, decision: Decision) -> None:
    session.add(decision)


def get_visible(session: Session, realm_ids: tuple[UUID, ...], decision_id: UUID) -> Decision | None:
    return session.scalars(
        select(Decision).where(Decision.id == decision_id, Decision.realm_id.in_(realm_ids))
    ).one_or_none()


def first_assessed(session: Session, realm_ids: tuple[UUID, ...]) -> list[Decision]:
    """Первая оценка каждой заявки контура с уровнем (без остановок по норме) — строка обучающей выборки."""
    return list(
        session.scalars(
            select(Decision)
            .where(Decision.realm_id.in_(realm_ids), Decision.outcome == "assessed", Decision.point.in_(("T1", "T4")))
            .ext(distinct_on(Decision.application_id))
            .order_by(Decision.application_id, Decision.as_of)
        )
    )


def latest_assessment_at(session: Session, realm_ids: tuple[UUID, ...]) -> datetime | None:
    found: datetime | None = session.scalar(
        select(func.max(Decision.as_of)).where(Decision.realm_id.in_(realm_ids), Decision.point.in_(("T1", "T4")))
    )
    return found


def level_counts(session: Session, realm_ids: tuple[UUID, ...], since: datetime) -> list[tuple[date, str | None, int]]:
    day = func.date(Decision.as_of)
    rows = session.execute(
        select(day, Decision.level, func.count())
        .where(Decision.realm_id.in_(realm_ids), Decision.point.in_(("T1", "T4")), Decision.as_of > since)
        .group_by(day, Decision.level)
        .order_by(day)
    )
    return [(d, level, count) for d, level, count in rows]


def feature_values(
    session: Session, realm_ids: tuple[UUID, ...], since: datetime, names: list[str]
) -> list[tuple[datetime, dict[str, Any]]]:
    values = Decision.record["inputs"]["features"]["values"]
    rows = session.execute(
        select(Decision.as_of, values).where(
            Decision.realm_id.in_(realm_ids), Decision.point.in_(("T1", "T4")), Decision.as_of > since
        )
    )
    return [(at, {n: v.get(n) for n in names}) for at, v in rows]
