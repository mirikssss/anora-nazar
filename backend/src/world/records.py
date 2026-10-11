"""Публичные записи мира: справочники для имитатора банка и правда о заявках для диагностики."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

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

    shared_identities и shared_roles — связи, которые типология заложила намеренно.
    """

    lender: str
    typology: Typology | None = None
    scheme_key: str | None = None
    shared_identities: tuple[IdentityKind, ...] = ()
    shared_roles: tuple[RoleKind, ...] = ()


@dataclass(frozen=True)
class OtherLenderApplication:
    """Заготовка заявки кредиторов Б и В для сети кредиторов (И4); в историю узла не входит."""

    id: str
    lender: str
    channel: Channel
    pinfl: str
    phone: str
    device_id: str | None
    amount: int
    occurred_at: datetime
