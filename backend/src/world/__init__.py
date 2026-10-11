"""Генератор синтетического мира: население, организации, три кредитора, месяцы истории, типологии F1–F3
с шумом и маскировкой, межбанковые схемы, ловушки, задержанные исходы.

Мир — значение в памяти: справочники и история кредитора узла в порядке получения. В базы его пишет
имитатор банка, прогоняя историю через интерфейсы узла. Одинаковые параметры — одинаковый мир.
"""

from dataclasses import dataclass
from random import Random

from shared.contracts.history import HistoryItem
from world.config import DEFAULT_PARAMS_PATH, PARAMS_DIR, WorldParams, load_params
from world.honest import plan_payroll_waves, plan_program_batches, plan_singles
from world.identifiers import Identifiers
from world.lenders import other_lender_applications
from world.organizations import build_organizations
from world.period import Calendar
from world.plans import ApplicationPlan, PlanFactory
from world.population import build_population
from world.records import (
    ApplicationTruth,
    BranchRecord,
    Channel,
    CrossLenderSummary,
    EmployeeRecord,
    HelperRecord,
    OtherLenderApplication,
    OtherLenderConfirmation,
    OtherLenderTransfer,
    SupplierRecord,
)
from world.sampling import scaled
from world.summary import cross_lender_summary
from world.timeline import assemble
from world.typologies.f1_coercion import plan_coercion
from world.typologies.f2_networks import plan_networks
from world.typologies.f3_programs import plan_schemes

__all__ = [
    "DEFAULT_PARAMS_PATH",
    "PARAMS_DIR",
    "ApplicationTruth",
    "BranchRecord",
    "CrossLenderSummary",
    "EmployeeRecord",
    "HelperRecord",
    "OtherLenderApplication",
    "OtherLenderConfirmation",
    "OtherLenderTransfer",
    "SupplierRecord",
    "World",
    "WorldParams",
    "generate",
    "load_params",
]


@dataclass(frozen=True)
class World:
    branches: list[BranchRecord]
    employees: list[EmployeeRecord]
    helpers: list[HelperRecord]
    suppliers: list[SupplierRecord]
    history: list[HistoryItem]  # только кредитор узла, по возрастанию received_at
    truth: dict[str, ApplicationTruth]  # внешний id заявки любого кредитора → правда генератора; в узел не уходит
    other_lenders: list[OtherLenderApplication]  # по кредиторам, внутри — по возрастанию occurred_at
    cross_lender_summary: CrossLenderSummary  # сводка межбанковых схем и ловушек сети; в узел не уходит


def _quotas(params: WorldParams, calendar: Calendar) -> dict[Channel, list[int]]:
    spec = params.applications
    return {
        "online": [scaled(spec.online_per_month, params.scale)] * calendar.months,
        "program": [scaled(spec.program_per_month, params.scale)] * calendar.months,
    }


def _missing(
    quotas: dict[Channel, list[int]], plans: list[ApplicationPlan], calendar: Calendar
) -> dict[Channel, list[int]]:
    """Сколько одиночных честных заявок добрать в каждый месяц канала после групп и типологий."""
    placed: dict[Channel, list[int]] = {channel: [0] * calendar.months for channel in quotas}
    for plan in plans:
        placed[plan.channel][calendar.month_index(plan.submitted_at)] += 1
    return {
        channel: [max(quota - done, 0) for quota, done in zip(quotas[channel], placed[channel], strict=True)]
        for channel in quotas
    }


def generate(params: WorldParams) -> World:
    rng = Random(params.seed)
    calendar = Calendar.from_params(params)
    ids = Identifiers(rng, params.population.phone_operator_codes)
    orgs = build_organizations(params, calendar, ids, rng)
    population = build_population(params, calendar, orgs, ids, rng)
    factory = PlanFactory(params, calendar, orgs, population, ids, rng)

    quotas = _quotas(params, calendar)
    online_total, program_total = sum(quotas["online"]), sum(quotas["program"])
    online_share = online_total / (online_total + program_total)
    plans = plan_coercion(factory, online_total)
    plans += plan_networks(factory, online_total + program_total, online_share)
    plans += plan_schemes(factory, program_total)
    plans += plan_payroll_waves(factory)
    plans += plan_program_batches(factory, round(program_total * params.organizations.normal_program_batches.share))
    # участники межбанковых схем у других кредиторов в квоту узла не входят
    elsewhere = [plan for plan in plans if plan.lender != factory.node_lender]
    plans = [plan for plan in plans if plan.lender == factory.node_lender]
    plans += plan_singles(factory, _missing(quotas, plans, calendar))

    timeline = assemble(params, calendar, orgs, plans, rng)
    others = other_lender_applications(factory, plans, elsewhere, online_share)
    return World(
        branches=list(orgs.branches),
        employees=list(orgs.employees),
        helpers=list(orgs.helpers),
        suppliers=list(orgs.suppliers.records),
        history=timeline.history,
        truth=timeline.truth | others.truth,
        other_lenders=others.applications,
        cross_lender_summary=cross_lender_summary(plans, others),
    )
