"""Факты источников по профилю клиента: бюро, траты по картам, взносы ИНПС, реестр юрлиц — в форматах контракта."""

from datetime import date, timedelta
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from shared.contracts.facts import (
    BureauReport,
    CardSpending,
    CompanyRecord,
    Contribution,
    InpsContributions,
    MonthlyAmount,
)

MONTHS_PER_YEAR = 12


class _Profile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BureauProfile(_Profile):
    active_loans: int = Field(ge=0)
    closed_loans: int = Field(ge=0)
    self_ban_lifted_days_ago: int | None = Field(default=None, ge=0)


class CardsProfile(_Profile):
    monthly_spending: int = Field(ge=0)
    months: int = Field(ge=1, le=36)


class IncomeJump(_Profile):
    """Скачок взносов в последние месяцы: рост зарплаты (обязательные) или добровольные взносы поверх (схема F3)."""

    months: int = Field(ge=1)
    factor: float = Field(gt=1)
    voluntary: bool


class InpsProfile(_Profile):
    monthly: int = Field(ge=0)
    months: int = Field(ge=1, le=60)
    jump: IncomeJump | None = None

    @model_validator(mode="after")
    def _jump_inside(self) -> Self:
        if self.jump is not None and self.jump.months > self.months:
            raise ValueError("Скачок взносов длиннее ряда")
        return self


class CompanyProfile(_Profile):
    registered_days_ago: int = Field(ge=0)
    headcount: int = Field(ge=0)
    headcount_year_ago: int | None = Field(default=None, ge=0)


class SourceProfile(_Profile):
    """Что источники банка знают о клиенте; нет раздела — источник клиента не знает и факта нет."""

    bureau: BureauProfile | None = None
    cards: CardsProfile | None = None
    inps: InpsProfile | None = None


def months_before(today: date, count: int) -> list[str]:
    """Полные месяцы до текущего, от старого к новому, в формате «ГГГГ-ММ»."""
    current = today.year * MONTHS_PER_YEAR + today.month - 1
    return [
        f"{index // MONTHS_PER_YEAR:04d}-{index % MONTHS_PER_YEAR + 1:02d}" for index in range(current - count, current)
    ]


def bureau_report(pinfl: str, profile: BureauProfile, today: date) -> BureauReport:
    lifted = profile.self_ban_lifted_days_ago
    return BureauReport(
        subject_pinfl=pinfl,
        active_loans=profile.active_loans,
        closed_loans=profile.closed_loans,
        self_ban_lifted_on=None if lifted is None else today - timedelta(days=lifted),
    )


def card_spending(pinfl: str, profile: CardsProfile, today: date) -> CardSpending:
    return CardSpending(
        subject_pinfl=pinfl,
        months=[
            MonthlyAmount(month=month, amount=profile.monthly_spending)
            for month in months_before(today, profile.months)
        ],
    )


def inps_contributions(pinfl: str, profile: InpsProfile, today: date) -> InpsContributions:
    months = months_before(today, profile.months)
    jump = profile.jump
    first_jumped = len(months) - (jump.months if jump is not None else 0)
    rows: list[Contribution] = []
    for index, month in enumerate(months):
        jumped = jump is not None and index >= first_jumped
        mandatory = profile.monthly
        if jump is not None and jumped and not jump.voluntary:
            mandatory = round(profile.monthly * jump.factor)
        rows.append(Contribution(month=month, amount=mandatory, voluntary=False))
        if jump is not None and jumped and jump.voluntary:
            rows.append(Contribution(month=month, amount=round(profile.monthly * (jump.factor - 1)), voluntary=True))
    return InpsContributions(subject_pinfl=pinfl, months=rows)


def company_record(inn: str, profile: CompanyProfile, today: date) -> CompanyRecord:
    return CompanyRecord(
        inn=inn,
        registered_on=today - timedelta(days=profile.registered_days_ago),
        headcount=profile.headcount,
        headcount_year_ago=profile.headcount_year_ago,
    )
