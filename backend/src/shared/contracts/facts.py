"""Факты источников банка — контракт событий, по которым узел считает признаки (Блок 3, «Источники данных»).

Источник отдаёт сводку на момент запроса банка: occurred_at — когда случилось, время получения ставит узел
(или прогон истории). Исправление — та же сущность со следующей entity_version.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Month = str  # «ГГГГ-ММ»
MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class _Fact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class _PersonFact(_Fact):
    subject_pinfl: str = Field(pattern=r"^\d{14}$")


class SessionSummary(_PersonFact):
    """Сессионный антифрод (№ 3759 п. 36–38) по сессии заявки."""

    application_id: str
    device_id: str
    device_first_seen_at: datetime
    access_recovered_at: datetime | None
    remote_control: bool
    call_in_progress: bool
    form_seconds: int | None = Field(default=None, ge=0)
    pasted: bool | None = None


class MonthlyAmount(_Fact):
    month: Month = Field(pattern=MONTH_PATTERN)
    amount: int = Field(ge=0)


class CardSpending(_PersonFact):
    """Траты по картам банка по месяцам; клиента без карты в банке источник не знает — факта нет."""

    months: list[MonthlyAmount]


class BureauReport(_PersonFact):
    active_loans: int = Field(ge=0)
    closed_loans: int = Field(ge=0)
    self_ban_lifted_on: date | None


class Contribution(MonthlyAmount):
    voluntary: bool | None


class InpsContributions(_PersonFact):
    """Взносы ИНПС через МИП; voluntary=None — источник не отличает добровольные от обязательных."""

    months: list[Contribution]


class CompanyRecord(_Fact):
    inn: str = Field(pattern=r"^\d{9}$")
    registered_on: date
    headcount: int = Field(ge=0)
    headcount_year_ago: int | None = Field(default=None, ge=0)


IncidentKind = Literal["law_enforcement", "client_report", "internal_control"]
IncidentResult = Literal["confirmed_fraud", "confirmed_coercion", "not_confirmed", "false_positive"]


class IncidentRecorded(_Fact):
    """Жалоба, документ органа или вывод проверки по выданным заявкам — источник меток с происхождением."""

    kind: IncidentKind
    typology: Literal["F1", "F2", "F3"]
    result: IncidentResult
    application_ids: list[str] = Field(min_length=1)
    case_key: str = Field(min_length=1, max_length=128)


class LoanMatured(_PersonFact):
    application_id: str
    missed_payments: int = Field(ge=0)


class FirstPaymentMissed(_PersonFact):
    application_id: str


FACTS: dict[str, type[_Fact]] = {
    "session.summary": SessionSummary,
    "cards.spending": CardSpending,
    "bureau.report": BureauReport,
    "inps.contributions": InpsContributions,
    "registry.company": CompanyRecord,
    "incident.recorded": IncidentRecorded,
    "loan.matured": LoanMatured,
    "loan.first_payment_missed": FirstPaymentMissed,
}
