"""Доступ к таблицам модуля."""

from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from node.modules.cases.domain import OPEN
from node.modules.cases.models import Case, CaseApplication, CaseEvent


def add(session: Session, row: Case | CaseApplication | CaseEvent) -> None:
    session.add(row)


def get_visible(session: Session, realm_id: UUID, case_id: UUID, *, lock: bool = False) -> Case | None:
    """Дела живут только в контуре посетителя: в общем мире их нет."""
    stmt = select(Case).where(Case.id == case_id, Case.realm_id == realm_id)
    if lock:
        stmt = stmt.with_for_update()
    return session.scalars(stmt).one_or_none()


def open_case_with(session: Session, realm_id: UUID, queue: str, application_ids: Iterable[UUID]) -> Case | None:
    ids = list(set(application_ids))
    if not ids:
        return None
    return session.scalars(
        select(Case)
        .join(CaseApplication, CaseApplication.case_id == Case.id)
        .where(
            Case.realm_id == realm_id,
            Case.queue == queue,
            Case.status.in_(OPEN),
            CaseApplication.application_id.in_(ids),
        )
        .order_by(Case.created_at)
        .limit(1)
    ).one_or_none()


def open_cases_of(session: Session, application_id: UUID) -> list[Case]:
    return list(
        session.scalars(
            select(Case)
            .join(CaseApplication, CaseApplication.case_id == Case.id)
            .where(CaseApplication.application_id == application_id, Case.status.in_(OPEN))
        )
    )


def member(session: Session, case_id: UUID, application_id: UUID) -> CaseApplication | None:
    return session.get(CaseApplication, (case_id, application_id))


def members(session: Session, case_ids: Iterable[UUID]) -> list[CaseApplication]:
    ids = list(set(case_ids))
    if not ids:
        return []
    return list(
        session.scalars(
            select(CaseApplication).where(CaseApplication.case_id.in_(ids)).order_by(CaseApplication.added_at)
        )
    )


def in_queue(session: Session, realm_id: UUID, queue: str) -> list[Case]:
    return list(
        session.scalars(select(Case).where(Case.realm_id == realm_id, Case.queue == queue, Case.status.in_(OPEN)))
    )


def events(session: Session, case_id: UUID) -> list[CaseEvent]:
    return list(session.scalars(select(CaseEvent).where(CaseEvent.case_id == case_id).order_by(CaseEvent.id)))


def overdue(session: Session, now: datetime) -> list[Case]:
    return list(
        session.scalars(
            select(Case).where(Case.status.in_(("open", "in_progress")), Case.due_at < now).with_for_update()
        )
    )


def counts_by_queue(session: Session, realm_id: UUID) -> dict[str, int]:
    result: dict[str, int] = {}
    for case in in_queue(session, realm_id, "online") + in_queue(session, realm_id, "group"):
        result[case.queue] = result.get(case.queue, 0) + 1
    return result


def released(session: Session, application_id: UUID, version: int) -> bool:
    found = session.scalar(
        select(CaseApplication.case_id)
        .where(
            CaseApplication.application_id == application_id,
            CaseApplication.decision == "release",
            CaseApplication.summary["version"].as_integer() == version,
        )
        .limit(1)
    )
    return found is not None
