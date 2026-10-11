"""Доступ к таблицам модуля."""

from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from node.modules.policy.models import PolicyProposal, PolicyVersion


def add(session: Session, row: PolicyProposal | PolicyVersion) -> None:
    session.add(row)


def version(session: Session, name: str) -> PolicyVersion | None:
    return session.get(PolicyVersion, name)


def latest_for(session: Session, realm_ids: tuple[UUID, ...], own: UUID) -> PolicyVersion | None:
    """Последняя утверждённая версия: своя песочница важнее общего мира."""
    return session.scalars(
        select(PolicyVersion)
        .where(PolicyVersion.realm_id.in_(realm_ids))
        .order_by(case((PolicyVersion.realm_id == own, 0), else_=1), PolicyVersion.created_at.desc())
        .limit(1)
    ).one_or_none()


def proposal_for_update(session: Session, proposal_id: UUID) -> PolicyProposal | None:
    return session.scalars(
        select(PolicyProposal).where(PolicyProposal.id == proposal_id).with_for_update()
    ).one_or_none()


def proposals(session: Session, realm_id: UUID) -> list[PolicyProposal]:
    return list(
        session.scalars(
            select(PolicyProposal)
            .where(PolicyProposal.realm_id == realm_id)
            .order_by(PolicyProposal.proposed_at.desc())
        )
    )
