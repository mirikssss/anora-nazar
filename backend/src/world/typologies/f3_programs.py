"""F3 — схема в программном займе.

Один помощник хокима, поставщик и товар на всю схему; цена за единицу обычно завышена против рынка, но часть
схем идёт по рыночной цене (маскировка). Часто поставщик
зарегистрирован незадолго до схемы, рекомендации помощника идут всплеском, заявитель не из его махалли,
а за несколько месяцев до заявки у заявителя растут добровольные взносы ИНПС.
"""

from dataclasses import replace

from world.organizations import registration_date
from world.plans import ApplicationPlan, PlanFactory, ProgramRoles
from world.sampling import between, chance, lognormal, pick


def scheme_sizes(factory: PlanFactory, program_total: int) -> list[int]:
    spec = factory.params.fraud.f3
    if program_total == 0 or spec.share_of_program == 0:
        return []
    sizes: list[int] = []
    while sum(sizes) < program_total * spec.share_of_program:
        sizes.append(between(factory.rng, spec.scheme_size))
    return sizes


def _scheme(factory: PlanFactory, key: str, size: int) -> list[ApplicationPlan]:
    spec, rng, orgs, population, calendar = (
        factory.params.fraud.f3,
        factory.rng,
        factory.orgs,
        factory.population,
        factory.calendar,
    )
    district = pick(rng, orgs.districts)
    helper = pick(rng, orgs.helpers_by_district[district.name])
    item = pick(rng, orgs.items)
    days = spec.burst_days if chance(rng, spec.helper_burst) else spec.spread_days
    overpriced = chance(rng, spec.overpriced)  # маскировка: часть схем идёт по рыночной цене
    first_day = calendar.window_start(rng, days)
    if chance(rng, spec.new_supplier):
        registered = registration_date(rng, factory.params.organizations.registration_age_days, first_day, new=True)
        supplier = orgs.suppliers.add(item.category, district.name, registered, pooled=False)
    else:
        supplier = orgs.suppliers.pick(rng, district.name, item.category)
    own_mahalla = population.by_mahalla.get((district.name, helper.mahalla), ())
    others = [i for i in population.by_district[district.name] if population.people[i].mahalla != helper.mahalla]
    everyone = range(len(population.people))
    plans: list[ApplicationPlan] = []
    for _ in range(size):
        outside = chance(rng, spec.outside_helper_mahalla)
        pools = [others, everyone] if outside else [own_mahalla, population.by_district[district.name]]
        person = population.sample(rng, pools, 1)[0]
        signals = factory.honest_signals()
        signals = replace(signals, income_jump="voluntary" if chance(rng, spec.income_jump) else None)
        roles = ProgramRoles(helper, supplier, orgs.employee_for(rng, district.name), item)
        moment = calendar.moment(rng, first_day, days, night=False)
        markup = lognormal(rng, spec.overprice) if overpriced else None
        plan = factory.program(person, moment, signals, roles, markup=markup)
        plans.append(replace(plan, typology="F3", scheme_key=key, shared_roles=("helper", "supplier")))
    return plans


def plan_schemes(factory: PlanFactory, program_total: int) -> list[ApplicationPlan]:
    plans: list[ApplicationPlan] = []
    for number, size in enumerate(scheme_sizes(factory, program_total), start=1):
        plans += _scheme(factory, f"F3-{number:03d}", size)
    return plans
