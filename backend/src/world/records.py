"""Публичные записи мира: справочники для имитатора банка и правда о заявках для диагностики."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from shared.contracts.network import Confirmation
from world.config import IdentityKind

Channel = Literal["online", "program"]
Typology = Literal["F1", "F2", "F3"]
RoleKind = Literal["employee", "helper", "supplier"]


@dataclass(frozen=True)
class BranchRecord:
    id: str
    name: str
    region: str
    district: str


@dataclass(frozen=True)
class EmployeeRecord:
    id: str
    branch_id: str
    display_name: str
    role: str


@dataclass(frozen=True)
class HelperRecord:
    """Помощник хокима; отвечает за одну махаллю района."""

    id: str
    district: str
    mahalla: str


@dataclass(frozen=True)
class SupplierRecord:
    inn: str
    name: str
    category: str
    district: str
    registered_on: date
    account: str
    headcount: int


@dataclass(frozen=True)
class ApplicationTruth:
    """Правда генератора о заявке — только для диагностики и тестов, в узел не уходит.

    shared_identities и shared_roles — связи, которые типология заложила намеренно; cross_lender — заявка
    из схемы, участники которой подают заявки у разных кредиторов.
    """

    lender: str
    typology: Typology | None = None
    scheme_key: str | None = None
    shared_identities: tuple[IdentityKind, ...] = ()
    shared_roles: tuple[RoleKind, ...] = ()
    cross_lender: bool = False


@dataclass(frozen=True)
class OtherLenderTransfer:
    """Первый перевод кредитных денег на карту (16 цифр); credit_share — доля кредита в переводе."""

    card: str
    credit_share: float
    occurred_at: datetime


@dataclass(frozen=True)
class OtherLenderConfirmation:
    """Результат закрытого дела у кредитора. kinds — какие идентификаторы заявки принадлежат мошеннику
    (из pinfl, phone, device, card, supplier_inn); идентификаторов жертвы в них нет."""

    typology: Typology
    confirmation: Confirmation
    confirmed_at: datetime
    kinds: list[str]


@dataclass(frozen=True)
class OtherLenderApplication:
    """Заявка кредиторов Б и В для сети кредиторов (И4); в историю узла не входит.

    issued_at, transfer и confirmation — только то, что случилось до конца периода мира.
    """

    id: str
    lender: str
    channel: Channel
    pinfl: str
    phone: str
    device_id: str | None
    amount: int
    occurred_at: datetime
    supplier_inn: str | None
    issued_at: datetime | None
    transfer: OtherLenderTransfer | None
    confirmation: OtherLenderConfirmation | None


@dataclass(frozen=True)
class CrossLenderSummary:
    """Сводка генератора по межбанковым схемам и ловушкам сети — для отчёта, в узел не уходит.

    Заявки кредитора узла в межбанковых схемах без локальной связи: node_unlinked — ни один их телефон, устройство
    или адрес не встречается в заявках других людей у этого кредитора; node_unlinked_in_scheme — не встречается
    в других заявках той же схемы у этого кредитора, то есть локальный граф схему не собирает. traps — заявки-ловушки
    у других кредиторов (comparison_same_hour, comparison_later, family) и число честных поставщиков с заёмщиками
    у всех кредиторов (popular_suppliers).
    """

    schemes: Mapping[Typology, int]
    node_applications: Mapping[Typology, int]
    node_unlinked: Mapping[Typology, int]
    node_unlinked_in_scheme: Mapping[Typology, int]
    other_applications: Mapping[str, int]
    other_fraud: Mapping[Typology, int]
    traps: Mapping[str, int]
    issued: int
    transfers: int
    mule_cards: int
    confirmations: int
