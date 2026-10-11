"""Факты источников банка по заявке: сессия, бюро, карты, ИНПС, реестр юрлиц (Блок 3, «Источники данных»)."""

from dataclasses import dataclass
from datetime import date, timedelta
from random import Random

from shared.contracts.facts import (
    BureauReport,
    CardSpending,
    CompanyRecord,
    Contribution,
    InpsContributions,
    MonthlyAmount,
    SessionSummary,
)
from world.config import WorldParams
from world.organizations import Company
from world.period import Calendar
from world.plans import ApplicationPlan
from world.sampling import between, noise, uniform


@dataclass(frozen=True)
class Source:
    """Источник и тип сущности факта в конверте события."""

    name: str
    entity_type: str


SESSION = Source("session", "session")
BUREAU = Source("bureau", "bureau_report")
CARDS = Source("cards", "card_spending")
INPS = Source("inps", "inps_contributions")
REGISTRY = Source("registry", "company")
INCIDENTS = Source("incidents", "incident")
CORE_BANKING = Source("core-banking", "loan")


def company_record(company: Company, as_of: date) -> CompanyRecord:
    return CompanyRecord(
        inn=company.inn,
        registered_on=company.registered_on,
        headcount=company.headcount,
        headcount_year_ago=company.headcount_year_ago(as_of),
    )


class SourceFacts:
    def __init__(self, params: WorldParams, calendar: Calendar, rng: Random) -> None:
        self._params = params
        self._calendar = calendar
        self._rng = rng

    def session(self, plan: ApplicationPlan, application_id: str) -> SessionSummary:
        if plan.device_id is None or plan.device_first_seen is None:
            raise ValueError(f"У онлайн-заявки {application_id} нет устройства сессии")
        spec, signals = self._params.session, plan.signals
        recovered = None
        if signals.access_recovered:
            recovered = plan.submitted_at - timedelta(hours=uniform(self._rng, spec.access_recovery_hours))
        return SessionSummary(
            subject_pinfl=plan.person.pinfl,
            application_id=application_id,
            device_id=plan.device_id,
            device_first_seen_at=plan.device_first_seen,
            access_recovered_at=recovered,
            remote_control=signals.remote_control,
            call_in_progress=signals.call_in_progress,
            form_seconds=between(self._rng, spec.fast_form_seconds if signals.pasted_fast else spec.form_seconds),
            pasted=signals.pasted_fast,
        )

    def bureau(self, plan: ApplicationPlan) -> BureauReport:
        spec, signals = self._params.bureau, plan.signals
        if signals.first_credit:
            active, closed = 0, 0
        elif signals.clean_history:
            # долгая чистая история: текущих долгов нет, закрытый кредит есть хотя бы один
            active, closed = 0, max(between(self._rng, spec.closed_loans), 1)
        else:
            active, closed = between(self._rng, spec.active_loans), between(self._rng, spec.closed_loans)
        lifted = None
        if signals.self_ban_lifted:
            local_day = self._calendar.local(plan.submitted_at).date()
            lifted = local_day - timedelta(days=between(self._rng, spec.self_ban_lifted_days))
        return BureauReport(
            subject_pinfl=plan.person.pinfl, active_loans=active, closed_loans=closed, self_ban_lifted_on=lifted
        )

    def cards(self, plan: ApplicationPlan) -> CardSpending:
        spec = self._params.sources
        months = self._calendar.months_before(plan.submitted_at, spec.card_months)
        spending = plan.person.monthly_spending
        return CardSpending(
            subject_pinfl=plan.person.pinfl,
            months=[
                MonthlyAmount(month=month, amount=round(spending * noise(self._rng, spec.spending_monthly_sigma)))
                for month in months
            ],
        )

    def inps(self, plan: ApplicationPlan) -> InpsContributions:
        """Взносы за месяцы до заявки. Скачок честного — рост зарплаты (обязательные взносы), скачок схемы F3 —
        добровольные взносы поверх; если источник их не различает, они сливаются с обязательными."""
        spec = self._params.sources
        distinguishable = self._params.population.inps_voluntary_distinguishable
        months = self._calendar.months_before(plan.submitted_at, spec.inps_months)
        base = plan.person.monthly_income * spec.inps_contribution_rate
        jump = plan.signals.income_jump
        factor = uniform(self._rng, spec.income_jump_factor) if jump else None
        rows: list[Contribution] = []
        for index, month in enumerate(months):
            amount = base * noise(self._rng, spec.inps_monthly_sigma)
            extra = 0.0
            if factor is not None and index >= len(months) - spec.income_jump_months:
                if jump == "mandatory":
                    amount *= factor
                else:
                    extra = base * (factor - 1)
            if extra and not distinguishable:
                amount, extra = amount + extra, 0.0
            rows.append(Contribution(month=month, amount=round(amount), voluntary=False if distinguishable else None))
            if extra:
                rows.append(Contribution(month=month, amount=round(extra), voluntary=True))
        return InpsContributions(subject_pinfl=plan.person.pinfl, months=rows)
