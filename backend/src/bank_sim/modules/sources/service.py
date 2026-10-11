"""Внешние источники через шлюз банка на синтетике: самозапрет и очередь бюро."""

from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from bank_sim.modules.sources import repository


def self_ban_status(session: Session, realm_id: UUID, pinfl: str) -> Literal["active", "none"]:
    record = repository.self_ban(session, realm_id, pinfl)
    return "active" if record is not None and record.status == "active" else "none"


def set_self_ban(session: Session, realm_id: UUID, pinfl: str, status: str, now: datetime) -> None:
    repository.set_self_ban(session, realm_id, pinfl, status, now)


def bureau_status(session: Session, realm_id: UUID, pinfl: str, now: datetime) -> Literal["free", "blocked"]:
    lock = repository.bureau_lock(session, realm_id, pinfl)
    return "blocked" if lock is not None and lock.locked_until > now else "free"


def lock_after_disbursement(session: Session, realm_id: UUID, pinfl: str, now: datetime, hours: int) -> None:
    repository.set_bureau_lock(session, realm_id, pinfl, now + timedelta(hours=hours))
