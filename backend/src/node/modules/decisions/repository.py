"""Доступ к таблицам модуля."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from node.modules.decisions.models import Decision


def add(session: Session, decision: Decision) -> None:
    session.add(decision)


def get_visible(session: Session, realm_ids: tuple[UUID, ...], decision_id: UUID) -> Decision | None:
    return session.scalars(
        select(Decision).where(Decision.id == decision_id, Decision.realm_id.in_(realm_ids))
    ).one_or_none()


def first_assessed(session: Session, realm_id: UUID) -> list[Decision]:
    """Первая оценка каждой заявки контура с уровнем (без остановок по норме) — строка обучающей выборки."""
    return list(
        session.scalars(
            select(Decision)
            .where(Decision.realm_id == realm_id, Decision.outcome == "assessed")
            .ext(distinct_on(Decision.application_id))
            .order_by(Decision.application_id, Decision.as_of)
        )
    )
