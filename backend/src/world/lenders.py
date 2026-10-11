"""Три условных кредитора. Историю получает только кредитор узла; заявки остальных — для сети кредиторов (И4).

Объём кредитора — по его доле рынка относительно доли кредитора узла. У других кредиторов, кроме фона честных
заявок, — участники межбанковых схем (их планируют типологии) и честные ловушки сети: человек сравнивает
условия двух банков, член семьи с общим телефоном или планшетом берёт кредит в другом банке, популярные честные
поставщики — у всех кредиторов (программные заявки фона выбирают поставщика так же, как честные у узла).

Выдача, первый перевод на карту и результаты дел — по разделу other_lenders параметров; без него у заявок
других кредиторов только сама заявка.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from world.config import Detection, IdentityKind, OtherLenders
from world.honest import honest_application
from world.outcomes import CONFIRMED
from world.plans import ApplicationPlan, PlanFactory
from world.population import Person, Population
from world.records import (
    ApplicationTruth,
    Channel,
    OtherLenderApplication,
    OtherLenderConfirmation,
    OtherLenderTransfer,
    RoleKind,
    Typology,
)
from world.sampling import chance, pick, uniform
from world.timeline import checks_passed, draw_checks

# Какие общие связи схемы — токены сети: адрес, сотрудник и помощник в сеть кредиторов не уходят.
IDENTITY_TOKENS: dict[IdentityKind, str] = {"phone": "phone", "device": "device"}
ROLE_TOKENS: dict[RoleKind, str] = {"supplier": "supplier_inn"}
CARD_TOKEN = "card"


@dataclass(frozen=True)
class _Draft:
    plan: ApplicationPlan
    declined: bool = False  # человек выбрал условия другого банка и кредит здесь не берёт
    trap: str | None = None


@dataclass(frozen=True)
class _Outcome:
    issued_at: datetime | None = None
    transfer: OtherLenderTransfer | None = None
    confirmation: OtherLenderConfirmation | None = None


@dataclass(frozen=True)
class OtherLenderWorld:
    applications: list[OtherLenderApplication]
    truth: dict[str, ApplicationTruth]
    traps: dict[str, int]


def _comparison(factory: PlanFactory, node_plans: list[ApplicationPlan]) -> list[_Draft]:
    """Ловушка: честный заёмщик узла подаёт онлайн-заявку ещё в один банк — в тот же час или через дни."""
    traps = factory.params.honest.cross_lender
    if traps is None:
        return []
    spec, rng = traps.comparison, factory.rng
    drafts: list[_Draft] = []
    for plan in node_plans:
        if plan.typology is not None or plan.channel != "online" or not chance(rng, spec.share):
            continue
        if chance(rng, spec.same_hour_share):
            trap, nearest, farthest = "comparison_same_hour", timedelta(), timedelta(minutes=spec.same_hour_minutes)
        else:
            low, high = spec.later_days
            trap, nearest, farthest = "comparison_later", timedelta(days=low), timedelta(days=high)
        moment = factory.calendar.around(rng, plan.submitted_at, nearest, farthest)
        if moment is not None:
            other = factory.online(plan.person, moment, factory.honest_signals())
            drafts.append(_Draft(replace(other, lender=factory.other_lender()), declined=True, trap=trap))
    return drafts


def _shared_households(population: Population) -> dict[int, list[Person]]:
    """Семьи с общим телефоном или планшетом: генератор населения выдаёт всем членам одно значение."""
    members: dict[int, list[Person]] = defaultdict(list)
    for person in population.people:
        members[person.household].append(person)
    return {
        household: people
        for household, people in members.items()
        if len(people) > 1 and (len({p.phone for p in people}) == 1 or len({p.device_id for p in people}) == 1)
    }


def _family(factory: PlanFactory, node_plans: list[ApplicationPlan]) -> list[_Draft]:
    """Ловушка: член семьи заёмщика узла берёт онлайн-кредит у другого кредитора с общего телефона или планшета."""
    traps = factory.params.honest.cross_lender
    if traps is None:
        return []
    spec, rng = traps.family, factory.rng
    households = _shared_households(factory.population)
    drafts: list[_Draft] = []
    for plan in node_plans:
        relatives = [p for p in households.get(plan.person.household, ()) if p.pinfl != plan.person.pinfl]
        if plan.typology is not None or not relatives or not chance(rng, spec.share):
            continue
        moment = factory.calendar.around(rng, plan.submitted_at, timedelta(), timedelta(days=spec.window_days))
        if moment is not None:
            signals = replace(factory.honest_signals(), new_device=False)  # заявка с общего устройства семьи
            relative = factory.online(pick(rng, relatives), moment, signals)
            drafts.append(_Draft(replace(relative, lender=factory.other_lender()), trap="family"))
    return drafts


def _background(factory: PlanFactory, lender: str, count: int, online_share: float) -> list[_Draft]:
    calendar, rng = factory.calendar, factory.rng
    drafts: list[_Draft] = []
    for _ in range(count):
        channel: Channel = "online" if chance(rng, online_share) else "program"
        plan = honest_application(factory, channel, calendar.start, calendar.days)
        drafts.append(_Draft(replace(plan, lender=lender)))
    return drafts


class _Execution:
    """Выдача, первый перевод и результаты дел у других кредиторов — только то, что случилось до конца периода."""

    def __init__(self, factory: PlanFactory, spec: OtherLenders, node_plans: list[ApplicationPlan]) -> None:
        self._factory = factory
        self._spec = spec
        self._rng = factory.rng
        self._calendar = factory.calendar
        self._node_applications: dict[str, list[datetime]] = defaultdict(list)
        for plan in node_plans:
            self._node_applications[plan.person.pinfl].append(plan.submitted_at)
        self._own_cards: dict[str, str] = {}
        self._mule_cards: dict[str, str] = {}

    def run(self, drafts: list[_Draft]) -> list[_Outcome]:
        issued = [self._issued_at(draft) for draft in drafts]
        transfers = [self._transfer(draft.plan, at) for draft, at in zip(drafts, issued, strict=True)]
        confirmations = self._confirmations([draft.plan for draft in drafts], issued, transfers)
        return [
            _Outcome(at, transfer, confirmations.get(index))
            for index, (at, transfer) in enumerate(zip(issued, transfers, strict=True))
        ]

    def _bureau_blocked(self, plan: ApplicationPlan) -> bool:
        """У узла заявка того же ПИНФЛ рядом по времени: бюро держит ПИНФЛ за узлом (№ 3759 п. 19–20)."""
        block = timedelta(hours=self._spec.bureau_block_hours)
        return any(abs(plan.submitted_at - at) < block for at in self._node_applications.get(plan.person.pinfl, ()))

    def _issued_at(self, draft: _Draft) -> datetime | None:
        plan = draft.plan
        if draft.declined or self._bureau_blocked(plan):
            return None
        if not checks_passed(draw_checks(self._rng, self._factory.params.applications.mandatory_failures)):
            return None
        delay = self._spec.issue_delay_minutes
        bounds = delay.online if plan.channel == "online" else delay.program
        at = plan.submitted_at + timedelta(minutes=uniform(self._rng, bounds))
        return at if self._calendar.contains(at) else None

    def _card(self, plan: ApplicationPlan) -> str:
        """Схема выводит деньги на общую карту мула, честный заёмщик — на свою карту."""
        if plan.scheme_key is not None:
            cards, key = self._mule_cards, plan.scheme_key
        else:
            cards, key = self._own_cards, plan.person.pinfl
        if key not in cards:
            cards[key] = self._factory.ids.card(self._spec.card_prefixes)
        return cards[key]

    def _transfer(self, plan: ApplicationPlan, issued_at: datetime | None) -> OtherLenderTransfer | None:
        if issued_at is None or plan.channel != "online":
            return None
        profile = self._spec.transfers.fraud if plan.scheme_key is not None else self._spec.transfers.honest
        if not chance(self._rng, profile.share):
            return None
        at = issued_at + timedelta(minutes=uniform(self._rng, profile.delay_minutes))
        if not self._calendar.contains(at):
            return None
        return OtherLenderTransfer(self._card(plan), uniform(self._rng, profile.credit_share), at)

    def _detection(self, typology: Typology | None) -> Detection | None:
        """Результат в сеть — только по F2 и F3: у жертвы F1 кредит у других кредиторов не выдан, карты нет."""
        confirmations = self._spec.confirmations
        return {"F2": confirmations.f2, "F3": confirmations.f3}.get(typology) if typology else None

    def _confirmations(
        self, plans: list[ApplicationPlan], issued: list[datetime | None], transfers: list[OtherLenderTransfer | None]
    ) -> dict[int, OtherLenderConfirmation]:
        """Дело — выданные заявки одной схемы у одного кредитора; раскрыто с долей и задержкой типологии."""
        cases: dict[str, list[int]] = defaultdict(list)
        for index, plan in enumerate(plans):
            if issued[index] is not None and plan.scheme_key is not None and self._detection(plan.typology) is not None:
                cases[plan.scheme_key].append(index)
        confirmed: dict[int, OtherLenderConfirmation] = {}
        for members in cases.values():
            typology = plans[members[0]].typology
            detection = self._detection(typology)
            if typology is None or detection is None or not chance(self._rng, detection.detected):
                continue
            last = max(at for index in members if (at := issued[index]) is not None)
            confirmed_at = last + timedelta(days=uniform(self._rng, detection.delay_days))
            if not self._calendar.contains(confirmed_at):
                continue
            for index in members:
                kinds = _fraudster_kinds(plans[index], transfers[index])
                if kinds:
                    confirmed[index] = OtherLenderConfirmation(typology, CONFIRMED[typology], confirmed_at, kinds)
        return confirmed


def _fraudster_kinds(plan: ApplicationPlan, transfer: OtherLenderTransfer | None) -> list[str]:
    """Идентификаторы заявки, принадлежащие мошеннику: общие связи схемы и карта мула; ПИНФЛ заёмщика — нет."""
    kinds = [IDENTITY_TOKENS[kind] for kind in plan.shared_identities if kind in IDENTITY_TOKENS]
    kinds += [ROLE_TOKENS[role] for role in plan.shared_roles if role in ROLE_TOKENS]
    return [*kinds, CARD_TOKEN] if transfer is not None else kinds


def _record(application_id: str, plan: ApplicationPlan, outcome: _Outcome) -> OtherLenderApplication:
    return OtherLenderApplication(
        id=application_id,
        lender=plan.lender,
        channel=plan.channel,
        pinfl=plan.person.pinfl,
        phone=plan.phone,
        device_id=plan.device_id,
        amount=plan.amount,
        occurred_at=plan.submitted_at,
        supplier_inn=plan.program.supplier.inn if plan.program is not None else None,
        issued_at=outcome.issued_at,
        transfer=outcome.transfer,
        confirmation=outcome.confirmation,
    )


def other_lender_applications(
    factory: PlanFactory, node_plans: list[ApplicationPlan], scheme_plans: list[ApplicationPlan], online_share: float
) -> OtherLenderWorld:
    """Заявки других кредиторов: участники межбанковых схем, честные ловушки сети и фон до доли рынка."""
    params = factory.params
    drafts = [_Draft(plan) for plan in scheme_plans] + _comparison(factory, node_plans) + _family(factory, node_plans)
    node_share = params.lender_share(factory.node_lender)
    others = [lender for lender in params.lenders if lender.code != factory.node_lender]
    for lender in others:
        quota = round(len(node_plans) * lender.share / node_share)
        placed = sum(1 for draft in drafts if draft.plan.lender == lender.code)
        drafts += _background(factory, lender.code, max(quota - placed, 0), online_share)
    execution = _Execution(factory, params.other_lenders, node_plans) if params.other_lenders else None
    applications: list[OtherLenderApplication] = []
    truth: dict[str, ApplicationTruth] = {}
    for lender in others:
        own = sorted((draft for draft in drafts if draft.plan.lender == lender.code), key=lambda d: d.plan.submitted_at)
        outcomes = execution.run(own) if execution is not None else [_Outcome() for _ in own]
        for number, (draft, outcome) in enumerate(zip(own, outcomes, strict=True), start=1):
            record = _record(f"W{lender.code}-{number:06d}", draft.plan, outcome)
            applications.append(record)
            truth[record.id] = draft.plan.truth()
    traps = Counter(draft.trap for draft in drafts if draft.trap is not None)
    return OtherLenderWorld(applications, truth, dict(traps))
