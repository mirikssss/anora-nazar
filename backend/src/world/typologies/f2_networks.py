"""F2 — подставные заёмщики и организованные группы, оба канала.

Кольцо с общими идентификаторами: участники подают заявки с редкого общего телефона, устройства или адреса
организатора за несколько дней; маскировка — только один вид общей связи. Координационное кольцо — без общих
идентификаторов: разные домохозяйства, только общие роли (сотрудник, помощник, поставщик) и всплеск во времени.

Межбанковое кольцо: организатор разносит участников по кредиторам, у кредитора узла — один-два, поэтому его
локальный индекс связей кольца почти не видит; общий телефон или устройство — поперёк банков. Такие кольца
добавляются к квоте узла: их участники у узла почти не меняют долю F2 узла.
"""

from dataclasses import dataclass, replace
from datetime import date

from world.config import IdentityKind
from world.organizations import District
from world.plans import ApplicationPlan, PlanFactory, ProgramRoles
from world.population import Person
from world.records import Channel, RoleKind
from world.sampling import between, chance, pick, portion

ROLES: tuple[RoleKind, ...] = ("employee", "helper", "supplier")
PROGRAM_IDENTITIES: tuple[IdentityKind, ...] = ("phone", "address")  # у программной заявки нет устройства сессии
NETWORK_IDENTITIES: tuple[IdentityKind, ...] = ("phone", "device")  # адрес в сеть кредиторов не уходит
MULTI_KIND_MIN = 2


@dataclass(frozen=True)
class _Ring:
    channel: Channel
    district: District
    first_day: date
    members: list[Person]


def ring_sizes(factory: PlanFactory, total_applications: int) -> list[int]:
    """Кольца набираются, пока их заявок меньше доли параметра; при доле координационных колец
    строго между 0 и 1 колец не меньше двух, чтобы в мире были обе разновидности."""
    spec = factory.params.fraud.f2
    if total_applications == 0 or spec.share_of_applications == 0:
        return []
    sizes: list[int] = []
    while sum(sizes) < total_applications * spec.share_of_applications:
        sizes.append(between(factory.rng, spec.ring_size))
    if 0 < spec.coordination_rings < 1 and len(sizes) < MULTI_KIND_MIN:
        sizes.append(between(factory.rng, spec.ring_size))
    return sizes


def _coordination_count(rings: int, share: float) -> int:
    if rings == 0:
        return 0
    count = round(rings * share)
    if share > 0:
        count = max(count, 1)
    if share < 1:
        count = min(count, rings - 1)
    return count


def _ring(factory: PlanFactory, channel: Channel, size: int, *, coordination: bool) -> _Ring:
    rng, population = factory.rng, factory.population
    district = pick(rng, factory.orgs.districts)
    pools = [population.by_district[district.name], range(len(population.people))]
    members = population.sample(rng, pools, size, distinct_households=coordination, exclude_dormitories=coordination)
    first_day = factory.calendar.window_start(rng, factory.params.fraud.f2.ring_days)
    return _Ring(channel, district, first_day, members)


def _available_kinds(factory: PlanFactory, channel: Channel, *, cross: bool) -> list[IdentityKind]:
    spec = factory.params.fraud.f2
    kinds = [kind for kind in spec.identity_kinds if channel == "online" or kind in PROGRAM_IDENTITIES]
    return [kind for kind in kinds if kind in NETWORK_IDENTITIES] if cross else kinds


def _identity_ring(factory: PlanFactory, ring: _Ring, *, cross: bool = False) -> list[ApplicationPlan]:
    spec, rng, calendar = factory.params.fraud.f2, factory.rng, factory.calendar
    available = _available_kinds(factory, ring.channel, cross=cross)
    if chance(rng, spec.single_kind_rings) or len(available) < MULTI_KIND_MIN:
        count = 1
    else:
        count = between(rng, (MULTI_KIND_MIN, len(available)))
    kinds = tuple(rng.sample(available, count))
    organizer = ring.members[0]
    shared_address = None
    if "address" in kinds:
        mahalla = pick(rng, ring.district.mahallas)
        shared_address = factory.population.addresses.household(ring.district.name, mahalla)
    shared_device = factory.ids.device() if "device" in kinds else None
    shared_employee = None
    if ring.channel == "program" and chance(rng, spec.shared_employee_share):
        shared_employee = factory.orgs.employee_for(rng, ring.district.name)
    roles: tuple[RoleKind, ...] = ("employee",) if shared_employee else ()
    plans: list[ApplicationPlan] = []
    for person in ring.members:
        signals = replace(factory.honest_signals(), first_credit=chance(rng, spec.first_credit))
        moment = calendar.moment(rng, ring.first_day, spec.ring_days, night=signals.night and ring.channel == "online")
        if ring.channel == "online":
            plan = factory.online(person, moment, signals)
        else:
            usual = factory.usual_roles(person)
            plan = factory.program(person, moment, signals, replace(usual, employee=shared_employee or usual.employee))
        if "phone" in kinds:
            plan = replace(plan, phone=organizer.phone)
        if shared_address is not None:
            plan = replace(plan, address=shared_address)
        if shared_device is not None:
            # устройство организатора для подставного заёмщика — новое: он им раньше не пользовался
            plan = replace(plan, device_id=shared_device, device_first_seen=factory.new_device(moment)[1])
        plans.append(replace(plan, shared_identities=kinds, shared_roles=roles))
    return plans


def _coordination_ring(factory: PlanFactory, ring: _Ring) -> list[ApplicationPlan]:
    spec, rng, orgs, calendar = factory.params.fraud.f2, factory.rng, factory.orgs, factory.calendar
    low, high = spec.coordination_shared_roles
    roles = tuple(rng.sample(ROLES, between(rng, (min(low, len(ROLES)), min(high, len(ROLES))))))
    item = pick(rng, orgs.items)
    shared = ProgramRoles(
        helper=pick(rng, orgs.helpers_by_district[ring.district.name]),
        supplier=orgs.suppliers.pick(rng, ring.district.name, item.category),
        employee=orgs.employee_for(rng, ring.district.name),
        item=item,
    )
    plans: list[ApplicationPlan] = []
    for person in ring.members:
        signals = replace(factory.honest_signals(), first_credit=chance(rng, spec.first_credit))
        moment = calendar.moment(rng, ring.first_day, spec.ring_days, night=False)
        usual = factory.usual_roles(person, item if "supplier" in roles else None)
        member_roles = ProgramRoles(
            helper=shared.helper if "helper" in roles else usual.helper,
            supplier=shared.supplier if "supplier" in roles else usual.supplier,
            employee=shared.employee if "employee" in roles else usual.employee,
            item=usual.item,
        )
        plans.append(replace(factory.program(person, moment, signals, member_roles), shared_roles=roles))
    return plans


def plan_networks(factory: PlanFactory, total_applications: int, online_share: float) -> list[ApplicationPlan]:
    """Координационные кольца — только в программах: у онлайн-заявки нет сотрудника, помощника и поставщика."""
    spec, rng = factory.params.fraud.f2, factory.rng
    sizes = ring_sizes(factory, total_applications)
    share = spec.coordination_rings if online_share < 1 else 0
    coordinated = set(rng.sample(range(len(sizes)), _coordination_count(len(sizes), share)))
    plans: list[ApplicationPlan] = []
    for index, size in enumerate(sizes):
        if index in coordinated:
            members = _coordination_ring(factory, _ring(factory, "program", size, coordination=True))
        else:
            channel: Channel = "online" if chance(rng, online_share) else "program"
            members = _identity_ring(factory, _ring(factory, channel, size, coordination=False))
        key = f"F2-{index + 1:03d}"
        plans += [replace(plan, typology="F2", scheme_key=key) for plan in members]
    return plans + _cross_rings(factory, len(sizes) - len(coordinated), online_share, len(sizes) + 1)


def _cross_rings(factory: PlanFactory, identity_rings: int, online_share: float, first: int) -> list[ApplicationPlan]:
    """Межбанковые кольца сверх квоты узла: их доля среди всех колец с общими идентификаторами — f2_rings."""
    cross = factory.params.fraud.cross_lender
    if cross is None:
        return []
    spec, rng = factory.params.fraud.f2, factory.rng
    plans: list[ApplicationPlan] = []
    for number in range(first, first + portion(identity_rings, cross.f2_rings / (1 - cross.f2_rings))):
        size = between(rng, spec.ring_size)
        channel: Channel = "online" if chance(rng, online_share) else "program"
        if not _available_kinds(factory, channel, cross=True):
            continue
        members = _identity_ring(factory, _ring(factory, channel, size, coordination=False), cross=True)
        node_members = min(between(rng, cross.f2_node_members), size - 1)
        key = f"F2-{number:03d}"
        for index, plan in enumerate(members):  # первый — организатор, его заявка у кредитора узла
            lender = factory.node_lender if index < node_members else factory.other_lender()
            plans.append(replace(plan, lender=lender, typology="F2", scheme_key=key, cross_lender=True))
    return plans
