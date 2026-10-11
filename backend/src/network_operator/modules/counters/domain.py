"""Чистая функция счётчиков (network-contract-1, «Счётчики»): без запросов наружу и без текущего времени.

- В счётчики не входят события самого запрашивающего кредитора — их он видит в своём индексе связей.
- Люди — разные токены ПИНФЛ заявителя события; сам заявитель запроса не считается.
- Учитывается версия события, действовавшая на as_of: получена до as_of, не отменена и не заменена исправлением.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from network_operator.modules.activity.domain import EventVersion, TokenKey
from network_operator.modules.confirmed.domain import ConfirmedFact
from shared.contracts.network import ConfirmedMatch, CounterName

Measure = Literal["lenders", "people"]


@dataclass(frozen=True)
class CounterSpec:
    """Смысл счётчика по контракту: по какому токену, какие события и что считаем. Окно — из конфигурации."""

    token_kind: str
    fact: str
    measure: Measure
    exclude_applicant: bool


# Смысл счётчиков фиксирует контракт network-contract-1; меняется только новой версией контракта.
COUNTERS: dict[CounterName, CounterSpec] = {
    "pinfl_lenders_1h": CounterSpec("pinfl", "application", "lenders", exclude_applicant=False),
    "pinfl_lenders_7d": CounterSpec("pinfl", "application", "lenders", exclude_applicant=False),
    "phone_people_24h": CounterSpec("phone", "application", "people", exclude_applicant=True),
    "phone_people_30d": CounterSpec("phone", "application", "people", exclude_applicant=True),
    "device_people_30d": CounterSpec("device", "application", "people", exclude_applicant=True),
    "card_borrowers_30d": CounterSpec("card", "transfer", "people", exclude_applicant=True),
    "card_lenders_30d": CounterSpec("card", "transfer", "lenders", exclude_applicant=True),
    "supplier_borrowers_30d": CounterSpec("supplier_inn", "application", "people", exclude_applicant=True),
    "supplier_lenders_30d": CounterSpec("supplier_inn", "application", "lenders", exclude_applicant=True),
}


@dataclass(frozen=True)
class QueryTokens:
    requester: str
    applicant: str  # токен ПИНФЛ заявителя запроса
    tokens: Sequence[TokenKey]  # включая ПИНФЛ заявителя
    as_of: datetime


def counters(
    query: QueryTokens,
    versions: Mapping[TokenKey, Sequence[EventVersion]],
    windows: Mapping[CounterName, timedelta],
) -> dict[CounterName, int]:
    result: dict[CounterName, int] = {}
    for name, spec in COUNTERS.items():
        start = query.as_of - windows[name]
        seen: set[str | None] = set()
        for key in query.tokens:
            if key[0] != spec.token_kind:
                continue
            for version in versions.get(key, ()):
                if (
                    version.lender == query.requester
                    or version.fact != spec.fact
                    or version.occurred_at <= start
                    or not version.visible_at(query.as_of)
                    or (spec.exclude_applicant and version.subject == query.applicant)
                ):
                    continue
                seen.add(version.lender if spec.measure == "lenders" else version.subject)
        result[name] = len(seen)
    return result


def confirmed_matches(query: QueryTokens, facts: Mapping[TokenKey, Sequence[ConfirmedFact]]) -> list[ConfirmedMatch]:
    """Токен запроса есть в результате проверки другого кредитора, подтверждённом и полученном до as_of."""
    found = {
        (fact.kind, fact.typology, fact.confirmation)
        for key in query.tokens
        for fact in facts.get(key, ())
        if fact.lender != query.requester and fact.visible_at(query.as_of)
    }
    return [
        ConfirmedMatch.model_validate({"kind": kind, "typology": typology, "confirmation": confirmation})
        for kind, typology, confirmation in sorted(found)
    ]


def counter_names_for(kinds: set[str]) -> list[str]:
    """Какие счётчики запрос вообще мог посчитать — для журнала запросов, без значений."""
    return sorted(name for name, spec in COUNTERS.items() if spec.token_kind in kinds)
