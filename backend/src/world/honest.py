"""Честные заявки: одиночные онлайн и программные, а также честные группы-ловушки —
волны зарплатных проектов и обычные программные партии.
"""

from world.plans import ApplicationPlan, PlanFactory, ProgramRoles
from world.records import Channel
from world.sampling import between, pick, scaled


def plan_payroll_waves(factory: PlanFactory) -> list[ApplicationPlan]:
    """Волна онлайн-заявок сотрудников одного работодателя за несколько дней — честная, но похожа на группу."""
    params, rng, population = factory.params, factory.rng, factory.population
    spec = params.organizations.payroll_projects
    if params.applications.online_per_month == 0 or not population.by_employer:
        return []
    candidates = [inn for inn, staff in population.by_employer.items() if len(staff) >= spec.wave_size[0]]
    if not candidates:
        candidates = [max(population.by_employer, key=lambda inn: len(population.by_employer[inn]))]
    plans: list[ApplicationPlan] = []
    for _ in range(scaled(spec.count, params.scale)):
        staff = population.by_employer[pick(rng, candidates)]
        first_day = factory.calendar.window_start(rng, spec.wave_days)
        for person in population.sample(rng, [staff], between(rng, spec.wave_size)):
            signals = factory.honest_signals()
            moment = factory.calendar.moment(rng, first_day, spec.wave_days, night=signals.night)
            plans.append(factory.online(person, moment, signals))
    return plans


def plan_program_batches(factory: PlanFactory, target: int) -> list[ApplicationPlan]:
    """Обычная программная партия: один помощник, поставщик, товар и сотрудник за неделю — честная."""
    rng, orgs, population = factory.rng, factory.orgs, factory.population
    spec = factory.params.organizations.normal_program_batches
    plans: list[ApplicationPlan] = []
    while len(plans) < target:
        district = pick(rng, orgs.districts)
        helper = pick(rng, orgs.helpers_by_district[district.name])
        item = pick(rng, orgs.items)
        roles = ProgramRoles(
            helper=helper,
            supplier=orgs.suppliers.pick(rng, district.name, item.category),
            employee=orgs.employee_for(rng, district.name),
            item=item,
        )
        first_day = factory.calendar.window_start(rng, spec.days)
        pools = [population.by_mahalla.get((district.name, helper.mahalla), ()), population.by_district[district.name]]
        for person in population.sample(rng, pools, between(rng, spec.size)):
            moment = factory.calendar.moment(rng, first_day, spec.days, night=False)
            plans.append(factory.program(person, moment, factory.honest_signals(), roles))
    return plans


def _single(factory: PlanFactory, channel: Channel, month: int) -> ApplicationPlan:
    rng = factory.rng
    first_day, days = factory.calendar.month_window(month)
    person = factory.population.random(rng)
    signals = factory.honest_signals()
    if channel == "online":
        return factory.online(person, factory.calendar.moment(rng, first_day, days, night=signals.night), signals)
    moment = factory.calendar.moment(rng, first_day, days, night=False)
    return factory.program(person, moment, signals, factory.usual_roles(person))


def plan_singles(factory: PlanFactory, missing: dict[Channel, list[int]]) -> list[ApplicationPlan]:
    """Одиночные честные заявки добирают месячную квоту канала до параметра объёма."""
    return [
        _single(factory, channel, month)
        for channel, per_month in missing.items()
        for month, count in enumerate(per_month)
        for _ in range(count)
    ]
