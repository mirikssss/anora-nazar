"""Карты клиентов: счёт, зачисление кредита, списание перевода, известные получатели."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from bank_sim.modules.cards import repository
from bank_sim.modules.cards.models import CardAccount, CardCredit
from shared.errors import ConflictError, NotFoundError


def open_account(session: Session, realm_id: UUID, pinfl: str, account: str, balance: int, now: datetime) -> None:
    """Счёт открывается один раз; уже открытый не трогаем."""
    repository.add_account_if_new(session, realm_id, account, pinfl, balance, now)


def credit(
    session: Session,
    realm_id: UUID,
    *,
    application_id: str,
    pinfl: str,
    account: str,
    amount: int,
    opening_balance: int,
    now: datetime,
) -> None:
    """Зачисление исполненного кредита. По одной заявке — одно зачисление (контракт единственной проводки)."""
    if repository.credit(session, realm_id, application_id) is not None:
        return
    repository.add_account_if_new(session, realm_id, account, pinfl, opening_balance, now)
    card = _locked(session, realm_id, account)
    repository.add_credit(
        session,
        CardCredit(
            realm_id=realm_id,
            application_id=application_id,
            account=account,
            pinfl=pinfl,
            amount=amount,
            balance_before=card.balance,
            credited_at=now,
        ),
    )
    card.balance += amount
    card.updated_at = now


def credit_for(session: Session, realm_id: UUID, application_id: str) -> CardCredit | None:
    return repository.credit(session, realm_id, application_id)


def balance(session: Session, realm_id: UUID, account: str) -> int:
    card = repository.account(session, realm_id, account)
    return 0 if card is None else card.balance


def is_known_recipient(session: Session, realm_id: UUID, pinfl: str, card: str) -> bool:
    return repository.recipient_known(session, realm_id, pinfl, card)


def remember_recipients(session: Session, realm_id: UUID, pinfl: str, cards: list[str], now: datetime) -> None:
    for card in cards:
        repository.add_recipient_if_new(session, realm_id, pinfl, card, now)


def debit(
    session: Session, realm_id: UUID, *, account: str, pinfl: str, recipient_card: str, amount: int, now: datetime
) -> None:
    """Списание перевода под блокировкой счёта; получатель становится известным."""
    card = _locked(session, realm_id, account)
    if card.balance < amount:
        raise ConflictError("insufficient_funds", "На карте недостаточно средств для перевода")
    card.balance -= amount
    card.updated_at = now
    repository.add_recipient_if_new(session, realm_id, pinfl, recipient_card, now)


def _locked(session: Session, realm_id: UUID, account: str) -> CardAccount:
    card = repository.account(session, realm_id, account, lock=True)
    if card is None:
        raise NotFoundError("card_account_not_found", "Карточный счёт не найден")
    return card
