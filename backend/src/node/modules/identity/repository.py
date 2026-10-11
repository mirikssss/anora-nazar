"""Доступ к таблицам модуля."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from node.modules.identity.models import ApiClient, StaffRole, StaffUser


def upsert_role(session: Session, values: dict[str, object]) -> None:
    stmt = insert(StaffRole).values(**values)
    session.execute(stmt.on_conflict_do_update(index_elements=[StaffRole.code], set_=dict(stmt.excluded)))


def upsert_user(session: Session, values: dict[str, object]) -> None:
    stmt = insert(StaffUser).values(**values)
    session.execute(stmt.on_conflict_do_update(index_elements=[StaffUser.code], set_=dict(stmt.excluded)))


def upsert_client(session: Session, values: dict[str, object]) -> None:
    stmt = insert(ApiClient).values(**values)
    session.execute(stmt.on_conflict_do_update(index_elements=[ApiClient.name], set_=dict(stmt.excluded)))


def client_by_key_hash(session: Session, key_hash: str) -> ApiClient | None:
    return session.scalars(select(ApiClient).where(ApiClient.key_hash == key_hash)).one_or_none()


def user_with_role(session: Session, user_code: str) -> tuple[StaffUser, StaffRole] | None:
    row = session.execute(
        select(StaffUser, StaffRole)
        .join(StaffRole, StaffRole.code == StaffUser.role_code)
        .where(StaffUser.code == user_code)
    ).one_or_none()
    return None if row is None else (row[0], row[1])


def roles_with_users(session: Session) -> list[tuple[StaffRole, list[StaffUser]]]:
    roles = list(session.scalars(select(StaffRole).order_by(StaffRole.code)))
    users = list(session.scalars(select(StaffUser).order_by(StaffUser.code)))
    return [(role, [u for u in users if u.role_code == role.code]) for role in roles]
