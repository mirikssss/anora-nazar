"""F3 — схема в программном займе.

Один помощник хокима, поставщик и товар на всю схему; цена за единицу обычно завышена против рынка, но часть
схем идёт по рыночной цене (маскировка). Часто поставщик
зарегистрирован незадолго до схемы, рекомендации помощника идут всплеском, заявитель не из его махалли,
а за несколько месяцев до заявки у заявителя растут добровольные взносы ИНПС.

Межбанковая схема: поставщик той же схемы за несколько недель получает заёмщиков и у других кредиторов.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta

from world.organizations import CatalogItem, District, registration_date
from world.plans import ApplicationPlan, PlanFactory, ProgramRoles
from world.records import HelperRecord, SupplierRecord
from world.sampling import between, chance, lognormal, pick, portion


@dataclass(frozen=True)
class _Scheme:
    key: str
    district: District
    helper: HelperRecord
    supplier: SupplierRecord
    item: CatalogItem
    first_day: date
    days: int
    overpriced: bool
    own_mahalla: Sequence[int]
    others: Sequence[int]


def scheme_sizes(factory: PlanFactory, program_total: int) -> list[int]:
    spec = factory.params.fraud.f3
    if program_total == 0 or spec.share_of_program == 0:
        return []
    sizes: list[int] = []
    while sum(sizes) < program_total * spec.share_of_program:
        sizes.append(between(factory.rng, spec.scheme_size))
    return sizes


def _open(factory: PlanFactory, key: str) -> _Scheme:
    spec, rng, orgs, population = factory.params.fraud.f3, factory.rng, factory.orgs, factory.population
    district = pick(rng, orgs.districts)
    helper = pick(rng, orgs.helpers_by_district[district.name])
    item = pick(rng, orgs.items)
    days = spec.burst_days if chance(rng, spec.helper_burst) else spec.spread_days
    overpriced = chance(rng, spec.overpriced)  # маскировка: часть схем идёт по рыночной цене
    first_day = factory.calendar.window_start(rng, days)
    if chance(rng, spec.new_supplier):
        registered = registration_date(rng, factory.params.organizations.registration_age_days, first_day, new=True)
        supplier = orgs.suppliers.add(item.category, district.name, registered, pooled=False)
    else:
        supplier = orgs.suppliers.pick(rng, district.name, item.category)
    return _Scheme(
        key=key,
        district=district,
        helper=helper,
        supplier=supplier,
        item=item,
        first_day=first_day,
        days=days,
        overpriced=overpriced,
        own_mahalla=population.by_mahalla.get((district.name, helper.mahalla), ()),
        others=[i for i in population.by_district[district.name] if population.people[i].mahalla != helper.mahalla],
    )


def _borrower(factory: PlanFactory, scheme: _Scheme, at: datetime | None = None) -> ApplicationPlan:
    """Заёмщик схемы; без `at` — момент в окне схемы."""
    spec, rng, population = factory.params.fraud.f3, factory.rng, factory.population
    district = scheme.district.name
    if chance(rng, spec.outside_helper_mahalla):
        pools = [scheme.others, range(len(population.people))]
    else:
        pools = [scheme.own_mahalla, population.by_district[district]]
    person = population.sample(rng, pools, 1)[0]
    signals = factory.honest_signals()
    signals = replace(signals, income_jump="voluntary" if chance(rng, spec.income_jump) else None)
    roles = ProgramRoles(scheme.helper, scheme.supplier, factory.orgs.employee_for(rng, district), scheme.item)
    moment = at if at is not None else factory.calendar.moment(rng, scheme.first_day, scheme.days, night=False)
    markup = lognormal(rng, spec.overprice) if scheme.overpriced else None
    plan = factory.program(person, moment, signals, roles, markup=markup)
    return replace(plan, typology="F3", scheme_key=scheme.key, shared_roles=("helper", "supplier"))


def _elsewhere(factory: PlanFactory, scheme: _Scheme, node_plans: list[ApplicationPlan]) -> list[ApplicationPlan]:
    """Заёмщики схемы у других кредиторов — рядом по времени с заявками схемы у кредитора узла."""
    cross, rng = factory.params.fraud.cross_lender, factory.rng
    if cross is None:
        return []
    window = timedelta(days=cross.f3_window_days)
    plans: list[ApplicationPlan] = []
    for _ in range(between(rng, cross.f3_other_borrowers)):
        moment = factory.calendar.around(rng, pick(rng, node_plans).submitted_at, timedelta(), window)
        if moment is not None:
            plan = _borrower(factory, scheme, moment)
            plans.append(replace(plan, lender=factory.other_lender(), cross_lender=True))
    return plans


def plan_schemes(factory: PlanFactory, program_total: int) -> list[ApplicationPlan]:
    schemes: list[tuple[_Scheme, list[ApplicationPlan]]] = []
    for number, size in enumerate(scheme_sizes(factory, program_total), start=1):
        scheme = _open(factory, f"F3-{number:03d}")
        schemes.append((scheme, [_borrower(factory, scheme) for _ in range(size)]))
    cross = factory.params.fraud.cross_lender
    chosen: set[int] = set()
    if cross is not None:
        chosen = set(factory.rng.sample(range(len(schemes)), portion(len(schemes), cross.f3_schemes)))
    plans: list[ApplicationPlan] = []
    for index, (scheme, members) in enumerate(schemes):
        elsewhere = _elsewhere(factory, scheme, members) if index in chosen else []
        plans += [replace(plan, cross_lender=bool(elsewhere)) for plan in members] + elsewhere
    return plans
