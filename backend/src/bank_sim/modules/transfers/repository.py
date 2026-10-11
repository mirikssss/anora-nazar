"""Доступ к таблицам модуля."""

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from bank_sim.modules.transfers.models import Transfer

EXECUTED = "executed"


def add(session: Session, transfer: Transfer) -> None:
    session.add(transfer)


def get(session: Session, realm_id: UUID, transfer_id: str, *, lock: bool = False) -> Transfer | None:
    stmt = select(Transfer).where(Transfer.realm_id == realm_id, Transfer.id == transfer_id)
    if lock:
        stmt = stmt.with_for_update()
    return session.scalars(stmt).one_or_none()


def has_executed(session: Session, realm_id: UUID, application_id: str) -> bool:
    return bool(
        session.scalar(
            select(
                exists().where(
                    Transfer.realm_id == realm_id,
                    Transfer.application_id == application_id,
                    Transfer.status == EXECUTED,
                )
            )
        )
    )


def list_for_realm(session: Session, realm_id: UUID, application_id: str | None) -> list[Transfer]:
    stmt = select(Transfer).where(Transfer.realm_id == realm_id).order_by(Transfer.created_at.desc())
    if application_id is not None:
        stmt = stmt.where(Transfer.application_id == application_id)
    return list(session.scalars(stmt))
