"""Сеть кредиторов в узле: что уходит в сеть и как ответ оператора становится признаками. Без ввода-вывода.

Контракт — network_operator/SPEC.md (network-contract-1). Узел шлёт только токены OPRF, получает только счётчики.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from shared.contracts.application import ApplicationSnapshot
from shared.contracts.network import ConfirmedMatch, CounterName, TokenKind

NetworkStatus = Literal["disabled", "ok", "unavailable"]
Value = float | int | bool | None

# Признак сети ← счётчик ответа; точки — где у признака есть смысл (Блок 3: сеть в Т1, Т2, Т4).
FEATURE_COUNTERS: dict[str, CounterName] = {
    "net_pinfl_lenders_1h": "pinfl_lenders_1h",
    "net_pinfl_lenders_7d": "pinfl_lenders_7d",
    "net_phone_people_24h": "phone_people_24h",
    "net_phone_people_30d": "phone_people_30d",
    "net_device_people_30d": "device_people_30d",
    "net_supplier_borrowers_30d": "supplier_borrowers_30d",
    "net_supplier_lenders_30d": "supplier_lenders_30d",
}
CONFIRMED_FEATURE = "net_confirmed_match"


class NetworkObservation(BaseModel):
    """Ответ сети на момент решения — входит в запись решения как есть."""

    model_config = ConfigDict(frozen=True)

    status: NetworkStatus
    as_of: datetime | None = None
    counters: dict[CounterName, int] = {}
    confirmed: list[ConfirmedMatch] = []
    error: str | None = None


def application_identifiers(snapshot: ApplicationSnapshot) -> list[tuple[TokenKind, str]]:
    """Идентификаторы заявки для сети: ПИНФЛ, телефон, устройство, ИНН поставщика программы."""
    items: list[tuple[TokenKind, str]] = [("pinfl", snapshot.applicant.pinfl), ("phone", snapshot.applicant.phone)]
    if snapshot.applicant.device_id is not None:
        items.append(("device", snapshot.applicant.device_id))
    if snapshot.program is not None:
        items.append(("supplier_inn", snapshot.program.supplier_inn))
    return items


def features(observation: NetworkObservation) -> dict[str, Value]:
    """Признаки сети; сеть выключена или не ответила — пропуски, модели с признаками сети не запускаются."""
    if observation.status != "ok":
        return {name: None for name in [*FEATURE_COUNTERS, CONFIRMED_FEATURE]}
    values: dict[str, Value] = {name: observation.counters.get(c, 0) for name, c in FEATURE_COUNTERS.items()}
    values[CONFIRMED_FEATURE] = bool(observation.confirmed)
    return values
