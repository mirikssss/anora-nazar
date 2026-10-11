"""Исходы и задержанные метки (Блок 3, «Метки»).

Инцидент — жалоба, документ органа или вывод проверки — приходит с задержкой относительно мошенничества.
Пропуск первого платежа — повод для проверки F2, не метка. Кредит без подтверждённого инцидента созревает
после окна наблюдения, в том числе у непойманных мошенников — это шум слабого негатива. Ловушки: ложные
срабатывания, неподтверждённые жалобы, честный пропуск первого платежа, поздние правки взносов ИНПС.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from random import Random

from shared.contracts.facts import (
    Contribution,
    FirstPaymentMissed,
    IncidentKind,
    IncidentRecorded,
    IncidentResult,
    InpsContributions,
    LoanMatured,
)
from world.config import TypologyOutcome, WorldParams
from world.plans import ApplicationPlan
from world.records import Channel, Typology
from world.sampling import chance, pick, uniform, weighted
from world.sink import HistorySink
from world.sources import CORE_BANKING, INCIDENTS, INPS, Source

CHANNEL_TYPOLOGIES: dict[Channel, tuple[Typology, ...]] = {"online": ("F1", "F2"), "program": ("F2", "F3")}
CONFIRMED: dict[Typology, IncidentResult] = {
    "F1": "confirmed_coercion",
    "F2": "confirmed_fraud",
    "F3": "confirmed_fraud",
}
COMPLAINT: IncidentKind = "client_report"


@dataclass(frozen=True)
class IssuedLoan:
    application_id: str
    plan: ApplicationPlan


@dataclass(frozen=True)
class ContributionsFact:
    """Отданный факт ИНПС — основа для поздней правки следующей версией."""

    entity_id: str
    entity_version: int
    payload: InpsContributions
    occurred_at: datetime
    received_at: datetime


class OutcomeWriter:
    def __init__(self, params: WorldParams, rng: Random, sink: HistorySink) -> None:
        self._params = params
        self._spec = params.outcomes
        self._rng = rng
        self._sink = sink
        self._incidents = 0

    def write(self, loans: list[IssuedLoan], contributions: list[ContributionsFact]) -> None:
        confirmed = self._fraud_incidents(loans)
        self._honest_incidents(loans)
        missed = self._first_payments(loans)
        self._maturity(loans, confirmed, missed)
        self._corrections(contributions)

    def _emit_loan_fact(self, payload: FirstPaymentMissed | LoanMatured, loan: IssuedLoan, at: datetime) -> None:
        self._emit(payload, CORE_BANKING, loan.application_id, at, at)

    def _emit(
        self,
        payload: IncidentRecorded | FirstPaymentMissed | LoanMatured | InpsContributions,
        source: Source,
        entity_id: str,
        occurred_at: datetime,
        received_at: datetime,
        entity_version: int | None = None,
    ) -> None:
        self._sink.fact(
            payload,
            source=source.name,
            entity_type=source.entity_type,
            entity_id=entity_id,
            entity_version=entity_version,
            occurred_at=occurred_at,
            received_at=received_at,
        )

    def _typology(self, typology: Typology) -> TypologyOutcome:
        return {"F1": self._spec.f1, "F2": self._spec.f2, "F3": self._spec.f3}[typology]

    def _incident(
        self, typology: Typology, kind: IncidentKind, result: IncidentResult, loans: list[IssuedLoan], case_key: str
    ) -> None:
        """Инцидент по делу: occurred_at — последняя заявка дела, received_at — позже на задержку типологии."""
        occurred = max(loan.plan.submitted_at for loan in loans)
        received = occurred + timedelta(days=uniform(self._rng, self._typology(typology).delay_days))
        self._incidents += 1
        payload = IncidentRecorded(
            kind=kind,
            typology=typology,
            result=result,
            application_ids=[loan.application_id for loan in loans],
            case_key=case_key,
        )
        self._emit(payload, INCIDENTS, f"INC-{self._incidents:06d}", occurred, received)

    def _fraud_incidents(self, loans: list[IssuedLoan]) -> set[str]:
        schemes: dict[str, list[IssuedLoan]] = {}
        for loan in loans:
            if loan.plan.typology is not None and loan.plan.scheme_key is not None:
                schemes.setdefault(loan.plan.scheme_key, []).append(loan)
        confirmed: set[str] = set()
        for key, group in schemes.items():
            typology = group[0].plan.typology
            if typology is None:
                continue
            spec = self._typology(typology)
            if chance(self._rng, spec.detected):
                self._incident(typology, weighted(self._rng, spec.kinds), CONFIRMED[typology], group, key)
                confirmed.update(loan.application_id for loan in group)
        return confirmed

    def _honest_incidents(self, loans: list[IssuedLoan]) -> None:
        for loan in loans:
            if loan.plan.typology is not None:
                continue
            if chance(self._rng, self._spec.false_alarm_share):
                typology = pick(self._rng, CHANNEL_TYPOLOGIES[loan.plan.channel])
                kind = weighted(self._rng, self._typology(typology).kinds)
                self._incident(typology, kind, "false_positive", [loan], f"{typology}-{loan.application_id}")
            if chance(self._rng, self._spec.unconfirmed_complaint_share):
                typology = pick(self._rng, CHANNEL_TYPOLOGIES[loan.plan.channel])
                self._incident(typology, COMPLAINT, "not_confirmed", [loan], f"{typology}-{loan.application_id}")

    def _misses_first_payment(self, plan: ApplicationPlan) -> bool:
        """Подставной заёмщик F2 не платит; честный иногда пропускает первый платёж — ловушка."""
        if plan.typology == "F2":
            return True
        return plan.typology is None and chance(self._rng, self._params.honest.first_payment_missed)

    def _first_payments(self, loans: list[IssuedLoan]) -> set[str]:
        missed: set[str] = set()
        for loan in loans:
            plan = loan.plan
            if not self._misses_first_payment(plan):
                continue
            at = plan.submitted_at + timedelta(days=uniform(self._rng, self._spec.f2.first_payment_missed_days))
            self._emit_loan_fact(
                FirstPaymentMissed(subject_pinfl=plan.person.pinfl, application_id=loan.application_id), loan, at
            )
            missed.add(loan.application_id)
        return missed

    def _maturity(self, loans: list[IssuedLoan], confirmed: set[str], missed: set[str]) -> None:
        for loan in loans:
            if loan.application_id in confirmed:
                continue
            plan = loan.plan
            window = (
                self._spec.observation_days.online if plan.channel == "online" else self._spec.observation_days.program
            )
            if plan.typology == "F2":
                missed_payments = window // self._spec.payment_interval_days
            else:
                missed_payments = 1 if loan.application_id in missed else 0
            payload = LoanMatured(
                subject_pinfl=plan.person.pinfl, application_id=loan.application_id, missed_payments=missed_payments
            )
            self._emit_loan_fact(payload, loan, plan.submitted_at + timedelta(days=window))

    def _corrections(self, contributions: list[ContributionsFact]) -> None:
        """Поздняя правка: та же сущность, следующая версия, взнос одного месяца исправлен."""
        for fact in contributions:
            if not fact.payload.months or not chance(self._rng, self._spec.inps_correction_share):
                continue
            rows = list(fact.payload.months)
            index = self._rng.randrange(len(rows))
            row = rows[index]
            amount = round(row.amount * uniform(self._rng, self._spec.inps_correction_factor))
            rows[index] = Contribution(month=row.month, amount=amount, voluntary=row.voluntary)
            received = fact.received_at + timedelta(days=uniform(self._rng, self._spec.inps_correction_delay_days))
            payload = InpsContributions(subject_pinfl=fact.payload.subject_pinfl, months=rows)
            self._emit(payload, INPS, fact.entity_id, fact.occurred_at, received, fact.entity_version + 1)
