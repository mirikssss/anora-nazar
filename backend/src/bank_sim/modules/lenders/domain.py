"""Чистая логика кредиторов Б и В: какие идентификаторы заявки токенизировать и какие события активности
и результаты дел уходят в сеть кредиторов (network-contract-1)."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from shared.contracts.network import TOKEN_KINDS, ActivityEvent, ConfirmedResult, TokenKind, TokenRef
from world.records import OtherLenderApplication

Refs = Mapping[tuple[TokenKind, str], TokenRef]
Channel = Literal["online", "program"]


@dataclass(frozen=True)
class LenderTransfer:
    card: str
    credit_share: float
    occurred_at: datetime


@dataclass(frozen=True)
class LenderConfirmation:
    typology: str
    confirmation: Literal["confirmed_fraud", "confirmed_coercion"]
    confirmed_at: datetime
    kinds: tuple[TokenKind, ...]  # идентификаторы мошенника; идентификаторов жертвы в сеть не отдаём


@dataclass(frozen=True)
class LenderApplication:
    """Заявка у кредитора Б или В — то, что о ней знает сеть: идентификаторы, моменты, канал."""

    id: str
    lender: str
    channel: Channel
    pinfl: str
    phone: str
    device_id: str | None
    supplier_inn: str | None
    occurred_at: datetime
    issued_at: datetime | None
    transfer: LenderTransfer | None
    confirmation: LenderConfirmation | None = None


def from_world(record: OtherLenderApplication) -> LenderApplication:
    transfer, confirmation = record.transfer, record.confirmation
    return LenderApplication(
        id=record.id,
        lender=record.lender,
        channel=record.channel,
        pinfl=record.pinfl,
        phone=record.phone,
        device_id=record.device_id,
        supplier_inn=record.supplier_inn,
        occurred_at=record.occurred_at,
        issued_at=record.issued_at,
        transfer=None
        if transfer is None
        else LenderTransfer(transfer.card, transfer.credit_share, transfer.occurred_at),
        confirmation=None
        if confirmation is None
        else LenderConfirmation(
            typology=confirmation.typology,
            confirmation=confirmation.confirmation,
            confirmed_at=confirmation.confirmed_at,
            kinds=tuple(k for k in TOKEN_KINDS if k in confirmation.kinds),
        ),
    )


def _values(app: LenderApplication) -> dict[TokenKind, str | None]:
    return {
        "pinfl": app.pinfl,
        "phone": app.phone,
        "device": app.device_id,
        "supplier_inn": app.supplier_inn,
        "card": None if app.transfer is None else app.transfer.card,
    }


def identifiers(app: LenderApplication) -> list[tuple[TokenKind, str]]:
    return [(kind, value) for kind, value in _values(app).items() if value is not None]


def events(app: LenderApplication, refs: Refs, delay: timedelta | None) -> list[ActivityEvent]:
    """Заявка, выдача и первый перевод. delay — задержка «событие → оператор» при прогоне истории (received_at);
    None — событие в реальном времени, время получения ставит оператор."""

    def received(moment: datetime) -> datetime | None:
        return None if delay is None else moment + delay

    def ref(kind: TokenKind, value: str | None) -> list[TokenRef]:
        return [] if value is None else [refs[(kind, value)]]

    subject = refs[("pinfl", app.pinfl)]
    supplier = ref("supplier_inn", app.supplier_inn)
    found = [
        ActivityEvent(
            event_id=f"{app.id}:application",
            kind="application",
            occurred_at=app.occurred_at,
            received_at=received(app.occurred_at),
            channel=app.channel,
            subject=subject,
            tokens=[*ref("phone", app.phone), *ref("device", app.device_id), *supplier],
        )
    ]
    if app.issued_at is not None:
        found.append(
            ActivityEvent(
                event_id=f"{app.id}:issuance",
                kind="issuance",
                occurred_at=app.issued_at,
                received_at=received(app.issued_at),
                channel=app.channel,
                subject=subject,
                tokens=supplier,
            )
        )
    if app.transfer is not None:
        found.append(
            ActivityEvent(
                event_id=f"{app.id}:transfer",
                kind="transfer",
                occurred_at=app.transfer.occurred_at,
                received_at=received(app.transfer.occurred_at),
                channel=app.channel,
                subject=subject,
                tokens=ref("card", app.transfer.card),
                credit_share=app.transfer.credit_share,
            )
        )
    return found


def confirmed_result(app: LenderApplication, refs: Refs) -> ConfirmedResult | None:
    """Результат закрытого дела — только токены идентификаторов мошенника."""
    if app.confirmation is None:
        return None
    values = _values(app)
    tokens = [refs[(kind, value)] for kind in app.confirmation.kinds if (value := values[kind]) is not None]
    if not tokens:
        return None
    return ConfirmedResult(
        result_id=f"{app.id}:result",
        typology=app.confirmation.typology,
        confirmation=app.confirmation.confirmation,
        tokens=tokens,
        confirmed_at=app.confirmation.confirmed_at,
    )
