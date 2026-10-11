"""Доступ к таблицам модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from node.modules.realms.models import SANDBOX, WORLD, Realm


def get(session: Session, realm_id: UUID) -> Realm | None:
    return session.get(Realm, realm_id)


def world(session: Session) -> Realm | None:
    return session.scalars(select(Realm).where(Realm.kind == WORLD)).one_or_none()


def insert_if_absent(session: Session, realm_id: UUID, kind: str, now: datetime) -> None:
    session.execute(
        insert(Realm).values(id=realm_id, kind=kind, created_at=now, last_seen_at=now).on_conflict_do_nothing()
    )


def touch(session: Session, realm_id: UUID, now: datetime) -> None:
    session.execute(update(Realm).where(Realm.id == realm_id).values(last_seen_at=now))


def delete_sandbox(session: Session, realm_id: UUID) -> int:
    result = session.execute(delete(Realm).where(Realm.id == realm_id, Realm.kind == SANDBOX))
    return int(result.rowcount)  # type: ignore[attr-defined]


def delete_inactive_sandboxes(session: Session, seen_before: datetime) -> list[UUID]:
    rows = session.execute(
        delete(Realm).where(Realm.kind == SANDBOX, Realm.last_seen_at < seen_before).returning(Realm.id)
    )
    return list(rows.scalars())


def existing(session: Session, ids: list[UUID]) -> set[UUID]:
    return set(session.scalars(select(Realm.id).where(Realm.id.in_(ids)))) if ids else set()
