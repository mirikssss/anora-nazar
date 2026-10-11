"""План заявки — что честный заёмщик или типология собирается подать и какому кредитору; фабрика планов
с общими правилами каналов.

План ещё без внешнего id и без обязательных шагов: их выдаёт сборка истории в порядке времени.
"""

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from random import Random
from typing import Literal

from world.config import BoundedLogNormal, IdentityKind, SessionParams, SignalProbabilities, WorldParams
from world.identifiers import Identifiers
from world.organizations import CatalogItem, Organizations, registration_date
from world.period import Calendar
from world.population import Person, Population
from world.records import ApplicationTruth, Channel, EmployeeRecord, HelperRecord, RoleKind, SupplierRecord, Typology
from world.sampling import chance, lognormal, noise, pick, uniform, weighted

IncomeJump = Literal["mandatory", "voluntary"]


@dataclass(frozen=True)
class Signals:
    """Признаки, которые источники покажут по заявке (Блок 3, зоны 1 и 3)."""

    access_recovered: bool
    new_device: bool
    remote_control: bool
    call_in_progress: bool
    night: bool
    first_credit: bool
    clean_history: bool
    self_ban_lifted: bool
    pasted_fast: bool
    amount_ratio: float  # сумма / медиана месячных трат по карте
    income_jump: IncomeJump | None


def draw_signals(rng: Random, profile: SignalProbabilities, session: SessionParams) -> Signals:
    remote_or_call = chance(rng, profile.remote_control_or_call)
    remote = remote_or_call and chance(rng, session.remote_control_share)
    return Signals(
        access_recovered=chance(rng, profile.access_recovery_hours_before),
        new_device=chance(rng, profile.new_device_days),
        remote_control=remote,
        call_in_progress=remote_or_call and not remote,
        night=chance(rng, profile.night),
        first_credit=chance(rng, profile.first_credit),
        clean_history=False,
        self_ban_lifted=chance(rng, profile.self_ban_lifted_30d),
        pasted_fast=chance(rng, profile.pasted_fast_form),
        amount_ratio=lognormal(rng, profile.amount_to_spending),
        income_jump=None,
    )


def round_amount(raw: float, bounds: BoundedLogNormal, step: int) -> int:
    return min(bounds.max, max(bounds.min, round(raw / step) * step))


@dataclass(frozen=True)
class ProgramPart:
    helper: HelperRecord
    supplier: SupplierRecord
    item: CatalogItem
    unit_price: int
    quantity: int

    @property
    def amount(self) -> int:
        return self.unit_price * self.quantity


@dataclass(frozen=True)
class ApplicationPlan:
    person: Person
    channel: Channel
    submitted_at: datetime
    branch_id: str
    employee_id: str | None
    phone: str
    device_id: str | None
    device_first_seen: datetime | None
    address: str
    amount: int
    term_months: int
    program: ProgramPart | None
    signals: Signals
    lender: str
    typology: Typology | None = None
    scheme_key: str | None = None
    shared_identities: tuple[IdentityKind, ...] = ()
    shared_roles: tuple[RoleKind, ...] = ()
    cross_lender: bool = False

    def truth(self) -> ApplicationTruth:
        return ApplicationTruth(
            lender=self.lender,
            typology=self.typology,
            scheme_key=self.scheme_key,
            shared_identities=self.shared_identities,
            shared_roles=self.shared_roles,
            cross_lender=self.cross_lender,
        )


@dataclass(frozen=True)
class ProgramRoles:
    helper: HelperRecord
    supplier: SupplierRecord
    employee: EmployeeRecord
    item: CatalogItem


class PlanFactory:
    """Общие правила каналов: онлайн — без филиала и сотрудника, программа — филиал района и цена товара."""

    def __init__(
        self,
        params: WorldParams,
        calendar: Calendar,
        orgs: Organizations,
        population: Population,
        ids: Identifiers,
        rng: Random,
    ) -> None:
        self.params = params
        self.calendar = calendar
        self.orgs = orgs
        self.population = population
        self.ids = ids
        self.rng = rng

    @property
    def node_lender(self) -> str:
        return self.params.applications.lender

    def other_lenders(self, count: int) -> list[str]:
        """До `count` разных кредиторов, кроме узла, — по долям рынка."""
        pool = {lender.code: lender.share for lender in self.params.lenders if lender.code != self.node_lender}
        chosen: list[str] = []
        while pool and len(chosen) < count:
            code = weighted(self.rng, pool)
            chosen.append(code)
            del pool[code]
        return chosen

    def other_lender(self) -> str:
        return self.other_lenders(1)[0]

    def honest_signals(self) -> Signals:
        signals = draw_signals(self.rng, self.params.honest, self.params.session)
        jump: IncomeJump | None = "mandatory" if chance(self.rng, self.params.honest.income_jump) else None
        return replace(signals, income_jump=jump)

    def online_amount(self, person: Person, ratio: float) -> int:
        """Сумма от трат по карте, если карта в банке; иначе — из общего распределения онлайн-сумм."""
        spec = self.params.applications
        raw = person.monthly_spending * ratio if person.card_in_bank else lognormal(self.rng, spec.online_amount)
        return round_amount(raw, spec.online_amount, spec.amount_step)

    def new_device(self, submitted_at: datetime) -> tuple[str, datetime]:
        age = timedelta(days=uniform(self.rng, self.params.session.new_device_age_days))
        return self.ids.device(), submitted_at - age

    def online(self, person: Person, submitted_at: datetime, signals: Signals) -> ApplicationPlan:
        device_id, first_seen = person.device_id, person.device_first_seen
        if signals.new_device:
            device_id, first_seen = self.new_device(submitted_at)
        return ApplicationPlan(
            person=person,
            channel="online",
            submitted_at=submitted_at,
            branch_id=self.params.applications.online_branch_id,
            employee_id=None,
            phone=person.phone,
            device_id=device_id,
            device_first_seen=first_seen,
            address=person.address,
            amount=self.online_amount(person, signals.amount_ratio),
            term_months=pick(self.rng, self.params.applications.online_terms),
            program=None,
            signals=signals,
            lender=self.node_lender,
        )

    def market_price(self, item: CatalogItem) -> float:
        return item.market_price * noise(self.rng, item.price_sigma)

    def usual_roles(self, person: Person, item: CatalogItem | None = None) -> ProgramRoles:
        """Обычный путь программной заявки: помощник своей махалли, поставщик района, сотрудник филиала района."""
        chosen = item or pick(self.rng, self.orgs.items)
        return ProgramRoles(
            helper=self.orgs.helper_of(person.district, person.mahalla),
            supplier=self.orgs.suppliers.pick(self.rng, person.district, chosen.category),
            employee=self.orgs.employee_for(self.rng, person.district),
            item=chosen,
        )

    def honest_roles(self, roles: ProgramRoles, district: str, day: date) -> ProgramRoles:
        """Ловушка: честная заявка у молодого поставщика, зарегистрированного незадолго до неё."""
        if not chance(self.rng, self.params.honest.young_supplier_share):
            return roles
        registered = registration_date(self.rng, self.params.organizations.registration_age_days, day, new=True)
        return replace(roles, supplier=self.orgs.suppliers.add(roles.item.category, district, registered, pooled=False))

    def honest_markup(self) -> float | None:
        """Ловушка: честная заявка с высокой ценой — премиальный товар, а не схема."""
        spec = self.params.honest.premium_price
        return lognormal(self.rng, spec.markup) if chance(self.rng, spec.share) else None

    def program(
        self,
        person: Person,
        submitted_at: datetime,
        signals: Signals,
        roles: ProgramRoles,
        markup: float | None = None,
    ) -> ApplicationPlan:
        price = self.market_price(roles.item) * (markup if markup is not None else 1)
        part = ProgramPart(
            helper=roles.helper,
            supplier=roles.supplier,
            item=roles.item,
            unit_price=round(price),
            quantity=self.rng.randint(*roles.item.quantity),
        )
        return ApplicationPlan(
            person=person,
            channel="program",
            submitted_at=submitted_at,
            branch_id=roles.employee.branch_id,
            employee_id=roles.employee.id,
            phone=person.phone,
            device_id=None,
            device_first_seen=None,
            address=person.address,
            amount=part.amount,
            term_months=pick(self.rng, self.params.applications.program_terms),
            program=part,
            signals=replace(signals, night=False),
            lender=self.node_lender,
        )
