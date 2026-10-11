"""Доступ к таблицам модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from bank_sim.modules.cards.models import CardAccount, CardCredit, CardRecipient


def add_account_if_new(session: Session, realm_id: UUID, account: str, pinfl: str, balance: int, now: datetime) -> None:
    session.execute(
        insert(CardAccount)
        .values(realm_id=realm_id, account=account, pinfl=pinfl, balance=balance, updated_at=now)
        .on_conflict_do_nothing()
    )


def account(session: Session, realm_id: UUID, number: str, *, lock: bool = False) -> CardAccount | None:
    stmt = select(CardAccount).where(CardAccount.realm_id == realm_id, CardAccount.account == number)
    if lock:
        stmt = stmt.with_for_update()
    return session.scalars(stmt).one_or_none()


def credit(session: Session, realm_id: UUID, application_id: str) -> CardCredit | None:
    return session.get(CardCredit, (realm_id, application_id))


def add_credit(session: Session, record: CardCredit) -> None:
    session.add(record)


def recipient_known(session: Session, realm_id: UUID, pinfl: str, card: str) -> bool:
    return session.get(CardRecipient, (realm_id, pinfl, card)) is not None


def add_recipient_if_new(session: Session, realm_id: UUID, pinfl: str, card: str, now: datetime) -> None:
    session.execute(
        insert(CardRecipient)
        .values(realm_id=realm_id, pinfl=pinfl, card=card, first_used_at=now)
        .on_conflict_do_nothing()
    )
