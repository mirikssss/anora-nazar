"""Доступ к таблицам модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from bank_sim.modules.sources.models import BureauLock, SelfBan


def self_ban(session: Session, realm_id: UUID, pinfl: str) -> SelfBan | None:
    return session.get(SelfBan, (realm_id, pinfl))


def set_self_ban(session: Session, realm_id: UUID, pinfl: str, status: str, now: datetime) -> None:
    stmt = insert(SelfBan).values(realm_id=realm_id, pinfl=pinfl, status=status, changed_at=now)
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=[SelfBan.realm_id, SelfBan.pinfl], set_={"status": status, "changed_at": now}
        )
    )


def bureau_lock(session: Session, realm_id: UUID, pinfl: str) -> BureauLock | None:
    return session.get(BureauLock, (realm_id, pinfl))


def set_bureau_lock(session: Session, realm_id: UUID, pinfl: str, until: datetime) -> None:
    stmt = insert(BureauLock).values(realm_id=realm_id, pinfl=pinfl, locked_until=until)
    session.execute(
        stmt.on_conflict_do_update(index_elements=[BureauLock.realm_id, BureauLock.pinfl], set_={"locked_until": until})
    )
