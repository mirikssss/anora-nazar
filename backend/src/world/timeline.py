"""Сборка истории кредитора узла.

Внешние id выдаются в порядке времени подачи. Перед оценкой — обязательные шаги № 3759 и факты источников,
которые банк спросил за несколько минут; реестр юрлиц — при первом появлении компании. Часть заявок получает
вторую версию. Затем исходы; история сортируется по (received_at, порядковый номер).
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from random import Random

from pydantic import BaseModel

from shared.contracts.application import Applicant, ApplicationSnapshot, Loan, MandatoryChecks, ProgramDetails
from shared.contracts.history import HistoryItem
from world.config import MandatoryFailures, WorldParams
from world.organizations import Organizations
from world.outcomes import ContributionsFact, IssuedLoan, OutcomeWriter
from world.period import Calendar
from world.plans import ApplicationPlan, round_amount
from world.records import ApplicationTruth
from world.sampling import chance, uniform
from world.sink import HistorySink
from world.sources import BUREAU, CARDS, INPS, REGISTRY, SESSION, Source, SourceFacts, company_record

FIRST_VERSION = 1


@dataclass(frozen=True)
class Timeline:
    history: list[HistoryItem]
    truth: dict[str, ApplicationTruth]


def draw_checks(rng: Random, spec: MandatoryFailures) -> MandatoryChecks:
    return MandatoryChecks(
        self_ban="active" if chance(rng, spec.self_ban_active) else "none",
        bureau="busy" if chance(rng, spec.bureau_busy) else "free",
        biometry="failed" if chance(rng, spec.biometry_failed) else "passed",
        phone_owner_match=not chance(rng, spec.phone_not_owned),
    )


def checks_passed(checks: MandatoryChecks) -> bool:
    return (
        checks.self_ban == "none"
        and checks.bureau == "free"
        and checks.biometry == "passed"
        and checks.phone_owner_match
    )


def build_snapshot(plan: ApplicationPlan, application_id: str, checks: MandatoryChecks) -> ApplicationSnapshot:
    program = None
    if plan.program is not None:
        part = plan.program
        program = ProgramDetails(
            helper_id=part.helper.id,
            supplier_inn=part.supplier.inn,
            supplier_account=part.supplier.account,
            item_code=part.item.code,
            unit=part.item.unit,
            unit_price=part.unit_price,
            quantity=part.quantity,
            district=part.helper.district,
        )
    online = plan.channel == "online"
    return ApplicationSnapshot(
        channel=plan.channel,
        branch_id=plan.branch_id,
        employee_id=plan.employee_id,
        applicant=Applicant(
            pinfl=plan.person.pinfl,
            phone=plan.phone,
            device_id=plan.device_id,
            address=plan.address,
            employer_inn=plan.person.employer_inn,
        ),
        loan=Loan(amount=plan.amount, term_months=plan.term_months),
        disbursement_account=plan.person.account if online else None,
        program=program,
        mandatory_checks=checks,
        session_refs=[application_id] if online else [],
    )


def changed_amount(plan: ApplicationPlan, params: WorldParams, factor: float) -> ApplicationPlan:
    """Вторая версия: заявитель меняет сумму, в программе — количество товара; новая сумма отличается от старой."""
    if plan.program is not None:
        quantity = max(round(plan.program.quantity * factor), 1)
        part = replace(plan.program, quantity=quantity if quantity != plan.program.quantity else quantity + 1)
        return replace(plan, program=part, amount=part.amount)
    spec = params.applications
    amount = round_amount(plan.amount * factor, spec.online_amount, spec.amount_step)
    if amount == plan.amount:
        amount = (
            amount - spec.amount_step
            if amount + spec.amount_step > spec.online_amount.max
            else amount + spec.amount_step
        )
    return replace(plan, amount=amount)


class _Assembler:
    def __init__(self, params: WorldParams, calendar: Calendar, orgs: Organizations, rng: Random) -> None:
        self._params = params
        self._orgs = orgs
        self._rng = rng
        self.sink = HistorySink(params.seed, params.version, calendar.end_at)
        self._facts = SourceFacts(params, calendar, rng)
        self._calendar = calendar
        self._known_companies: set[str] = set()
        self.loans: list[IssuedLoan] = []
        self.contributions: list[ContributionsFact] = []
        self.truth: dict[str, ApplicationTruth] = {}

    def add(self, application_id: str, plan: ApplicationPlan) -> None:
        self.truth[application_id] = ApplicationTruth(
            lender=self._params.applications.lender,
            typology=plan.typology,
            scheme_key=plan.scheme_key,
            shared_identities=plan.shared_identities,
            shared_roles=plan.shared_roles,
        )
        checks = draw_checks(self._rng, self._params.applications.mandatory_failures)
        self._source_facts(application_id, plan)
        self.sink.assessment(
            application_id, FIRST_VERSION, build_snapshot(plan, application_id, checks), plan.submitted_at
        )
        if not checks_passed(checks):
            return
        self.loans.append(IssuedLoan(application_id, plan))
        spec = self._params.applications
        if chance(self._rng, spec.second_version_share):
            revised = changed_amount(plan, self._params, uniform(self._rng, spec.second_version_amount_factor))
            at = plan.submitted_at + timedelta(minutes=uniform(self._rng, spec.second_version_delay_minutes))
            self.sink.assessment(application_id, FIRST_VERSION + 1, build_snapshot(revised, application_id, checks), at)

    def _asked_at(self, plan: ApplicationPlan) -> datetime:
        return plan.submitted_at - timedelta(minutes=uniform(self._rng, self._params.applications.source_lead_minutes))

    def _emit(
        self, payload: BaseModel, source: Source, entity_id: str, at: datetime, version: int | None = None
    ) -> None:
        self.sink.fact(
            payload,
            source=source.name,
            entity_type=source.entity_type,
            entity_id=entity_id,
            entity_version=version,
            occurred_at=at,
            received_at=at,
        )

    def _source_facts(self, application_id: str, plan: ApplicationPlan) -> None:
        companies = [plan.person.employer_inn, plan.program.supplier.inn if plan.program else None]
        for inn in companies:
            if inn is not None and inn not in self._known_companies:
                self._known_companies.add(inn)
                at = self._asked_at(plan)
                self._emit(company_record(self._orgs.company(inn), self._calendar.local(at).date()), REGISTRY, inn, at)
        if plan.channel == "online":
            self._emit(self._facts.session(plan, application_id), SESSION, application_id, self._asked_at(plan))
        self._emit(self._facts.bureau(plan), BUREAU, application_id, self._asked_at(plan))
        if plan.person.card_in_bank:
            self._emit(self._facts.cards(plan), CARDS, application_id, self._asked_at(plan))
        if plan.person.inps_available:
            payload = self._facts.inps(plan)
            at = self._asked_at(plan)
            entity_id = f"{plan.person.pinfl}:{application_id}"
            self._emit(payload, INPS, entity_id, at, FIRST_VERSION)
            self.contributions.append(ContributionsFact(entity_id, FIRST_VERSION, payload, at, at))


def assemble(
    params: WorldParams, calendar: Calendar, orgs: Organizations, plans: list[ApplicationPlan], rng: Random
) -> Timeline:
    assembler = _Assembler(params, calendar, orgs, rng)
    order = sorted(range(len(plans)), key=lambda index: (plans[index].submitted_at, index))
    for number, index in enumerate(order, start=1):
        assembler.add(f"W-{number:06d}", plans[index])
    OutcomeWriter(params, rng, assembler.sink).write(assembler.loans, assembler.contributions)
    return Timeline(history=assembler.sink.items(), truth=assembler.truth)
