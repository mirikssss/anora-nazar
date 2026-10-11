"""Чистая логика признаков: значения из фактов, собранных на момент as_of. Без ввода-вывода и без now().

Нет данных — не риск и не «чисто»: признак остаётся пустым (None), а недоступный источник попадает в
unavailable_sources (Блок 3, «Что делаем при отсутствии данных»).
"""

import math
import statistics
from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from node.modules.features.catalog import PASSPORTS
from node.modules.index.domain import GroupView, RoleConcentrations
from shared.config import load_yaml
from shared.contracts.application import ApplicationSnapshot
from shared.contracts.facts import BureauReport, CardSpending, CompanyRecord, InpsContributions, SessionSummary

Value = float | int | bool | None
Point = Literal["T1", "T4"]
CATALOG_DIR = Path(__file__).parent / "catalog"
SECONDS_PER_DAY = 86400


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Zone1Config(_Frozen):
    night_hours: tuple[int, int]
    spending_months: int = Field(gt=0)
    device_shared_window_days: int = Field(gt=0)


class PriceLevel(_Frozen):
    scope: Literal["district", "country"]
    days: int = Field(gt=0)


class PricingConfig(_Frozen):
    min_comparables: int = Field(gt=0)
    robust_z_flag: float = Field(gt=0)
    mad_scale: float = Field(gt=0)
    min_log_mad: float = Field(gt=0)
    levels: list[PriceLevel] = Field(min_length=1)


class IncomeConfig(_Frozen):
    recent_months: int = Field(gt=0)
    baseline_months: int = Field(gt=0)
    cusum_k: float = Field(ge=0)
    cusum_h: float = Field(gt=0)
    sigma_floor_share: float = Field(gt=0)


class ConcentrationConfig(_Frozen):
    window_days: int = Field(gt=0)
    prior_weight: float = Field(gt=0)
    prior_windows: float = Field(gt=0)


class Zone3Config(_Frozen):
    pricing: PricingConfig
    income: IncomeConfig
    concentration: ConcentrationConfig
    helper_burst_window_days: int = Field(gt=0)


class FeatureConfig(_Frozen):
    version: str
    timezone: str
    zone1: Zone1Config
    zone3: Zone3Config


def load_feature_config(version: str) -> FeatureConfig:
    return FeatureConfig.model_validate(load_yaml(CATALOG_DIR / f"{version}.yaml"))


FEATURE_SET_VERSION = "fs-2"


class FeatureVector(_Frozen):
    set_version: str
    point: Point | None = None  # нет в записях набора fs-1
    values: dict[str, Value]
    unavailable_sources: list[str] = []


class Facts(_Frozen):
    """Ответы источников на момент as_of; None — источник не ответил или клиента не знает."""

    session: SessionSummary | None = None
    cards: CardSpending | None = None
    bureau: BureauReport | None = None
    inps: InpsContributions | None = None
    supplier: CompanyRecord | None = None
    employer: CompanyRecord | None = None


def _days(later: datetime, earlier: datetime) -> float:
    return round((later - earlier).total_seconds() / SECONDS_PER_DAY, 3)


def robust_z(value: float, sample: list[float], cfg: PricingConfig) -> float:
    """Робастный z-балл на лог-шкале по медиане и MAD (Блок 3, зона 3)."""
    logs = [math.log(v) for v in sample]
    median = statistics.median(logs)
    mad = statistics.median(abs(x - median) for x in logs)
    return round((math.log(value) - median) / (cfg.mad_scale * max(mad, cfg.min_log_mad)), 4)


def price_features(unit_price: int, comparables: list[list[int]], cfg: PricingConfig) -> dict[str, Value]:
    """Первый уровень сравнения, где договоров достаточно; иначе цена не проверена."""
    for level, sample in enumerate(comparables, start=1):
        if len(sample) >= cfg.min_comparables:
            z = robust_z(unit_price, [float(v) for v in sample], cfg)
            return {"price_robust_z": z, "price_comparables_level": level, "price_above_market": z > cfg.robust_z_flag}
    return {"price_robust_z": None, "price_comparables_level": None, "price_above_market": None}


def cusum_alarm(series: list[float], mean: float, sigma: float, cfg: IncomeConfig) -> bool:
    """Односторонний CUSUM вверх по стандартизованному ряду."""
    level = 0.0
    for value in series:
        level = max(0.0, level + (value - mean) / sigma - cfg.cusum_k)
        if level > cfg.cusum_h:
            return True
    return False


def income_features(inps: InpsContributions | None, cfg: IncomeConfig) -> dict[str, Value]:
    empty: dict[str, Value] = {
        "income_jump_ratio": None,
        "income_cusum_alarm": None,
        "voluntary_contributions_share": None,
    }
    if inps is None:
        return empty
    months = sorted(inps.months, key=lambda m: m.month)
    recent = months[-cfg.recent_months :]
    baseline = months[-(cfg.recent_months + cfg.baseline_months) : -cfg.recent_months]
    if len(recent) < cfg.recent_months or not baseline:
        return empty
    base = [float(m.amount) for m in baseline]
    base_median = statistics.median(base)
    recent_median = statistics.median(float(m.amount) for m in recent)
    if base_median > 0:
        jump: float | None = round(recent_median / base_median, 4)
    else:
        jump = 1.0 if recent_median == 0 else None
    sigma = max(statistics.pstdev(base), cfg.sigma_floor_share * base_median)
    alarm = cusum_alarm([float(m.amount) for m in recent], base_median, sigma, cfg) if sigma > 0 else None
    total = sum(m.amount for m in recent)
    voluntary: float | None = None
    if total > 0 and all(m.voluntary is not None for m in recent):
        voluntary = round(sum(m.amount for m in recent if m.voluntary) / total, 4)
    return {"income_jump_ratio": jump, "income_cusum_alarm": alarm, "voluntary_contributions_share": voluntary}


def _company(record: CompanyRecord | None, as_of: datetime) -> tuple[float | None, float | None]:
    if record is None:
        return None, None
    age = float((as_of.date() - record.registered_on).days)
    growth = None
    if record.headcount_year_ago:
        growth = round(record.headcount / record.headcount_year_ago, 4)
    return age, growth


def zone1_features(
    snapshot: ApplicationSnapshot,
    as_of: datetime,
    facts: Facts,
    device_subjects: int | None,
    cfg: FeatureConfig,
) -> dict[str, Value]:
    session, cards, bureau = facts.session, facts.cards, facts.bureau
    local_hour = as_of.astimezone(ZoneInfo(cfg.timezone)).hour
    start, end = cfg.zone1.night_hours
    spending: float | None = None
    if cards is not None:
        months = sorted(cards.months, key=lambda m: m.month)[-cfg.zone1.spending_months :]
        median = statistics.median(m.amount for m in months) if months else 0
        spending = round(snapshot.loan.amount / median, 4) if median > 0 else None
    recovered = session.access_recovered_at if session is not None else None
    lifted = bureau.self_ban_lifted_on if bureau is not None else None
    return {
        "minutes_since_access_recovery": (
            None if recovered is None else round((as_of - recovered).total_seconds() / 60, 1)
        ),
        "device_age_days": None if session is None else _days(as_of, session.device_first_seen_at),
        "device_subjects_30d": device_subjects,
        "remote_control_or_call": (None if session is None else session.remote_control or session.call_in_progress),
        "form_seconds": None if session is None else session.form_seconds,
        "pasted_into_form": None if session is None else session.pasted,
        "amount_to_spending": spending,
        "first_credit": None if bureau is None else bureau.active_loans + bureau.closed_loans == 0,
        "days_since_self_ban_lifted": None if lifted is None else float((as_of.date() - lifted).days),
        "night_application": start <= local_hour < end,
    }


def zone2_features(view: GroupView, first_credit_share: float | None) -> dict[str, Value]:
    flagged = [c for c in view.coordination if c.flagged]
    return {
        "independent_rare_links": view.independent_rare_links,
        "rare_links_weight": round(sum(link.weight for link in view.rare_links), 4),
        "group_applications": view.group_applications,
        "group_subjects": view.group_subjects,
        "group_recent_applications": view.recent_applications,
        "group_background_per_window": view.background_per_window,
        "group_burst": view.burst,
        "group_shared_roles": len(view.shared_roles),
        "group_first_credit_share": first_credit_share,
        "coordination_max_ratio": max((c.ratio for c in view.coordination), default=None),
        "coordination_flagged_roles": len(flagged),
    }


def zone3_features(
    snapshot: ApplicationSnapshot,
    facts: Facts,
    prices: list[list[int]],
    concentrations: RoleConcentrations,
    as_of: datetime,
    cfg: FeatureConfig,
) -> dict[str, Value]:
    program = snapshot.program
    values: dict[str, Value] = {}
    if program is not None:
        values |= price_features(program.unit_price, prices, cfg.zone3.pricing)
        values |= {
            "supplier_age_days": _company(facts.supplier, as_of)[0],
            "supplier_concentration_ratio": concentrations.supplier_ratio,
            "branch_supplier_hhi": concentrations.branch_supplier_hhi,
            "employee_concentration_ratio": concentrations.employee_ratio,
            "helper_burst_ratio": concentrations.helper_burst_ratio,
            "helper_supplier_share": concentrations.helper_supplier_share,
        }
    employer_age, employer_growth = _company(facts.employer, as_of)
    values |= income_features(facts.inps, cfg.zone3.income)
    values |= {"employer_age_days": employer_age, "employer_headcount_growth": employer_growth}
    return values


def unavailable_sources(snapshot: ApplicationSnapshot, facts: Facts) -> list[str]:
    """Какие источники не ответили: показываются в причинах решения."""
    missing = []
    if snapshot.channel == "online" and facts.session is None:
        missing.append("session")
    if facts.bureau is None:
        missing.append("bureau")
    if facts.inps is None:
        missing.append("inps")
    if snapshot.program is not None and facts.supplier is None:
        missing.append("registry")
    return missing


SIGNALS = ("price_above_market",)


def assemble(
    point: Point, snapshot: ApplicationSnapshot, parts: dict[str, Value], facts: Facts
) -> tuple[FeatureVector, dict[str, Value]]:
    """Вектор точки — только признаки с паспортом этой точки; сигналы для правил продукта — отдельно."""
    context: dict[str, Value] = {
        "channel_online": snapshot.channel == "online",
        "loan_amount_log": round(math.log(snapshot.loan.amount), 4),
    }
    merged = context | parts
    unknown = merged.keys() - PASSPORTS.keys() - set(SIGNALS)
    if unknown:
        raise AssertionError(f"Признаки без паспорта: {sorted(unknown)}")
    values = {name: merged.get(name) for name, passport in PASSPORTS.items() if point in passport.points}
    vector = FeatureVector(
        set_version=FEATURE_SET_VERSION,
        point=point,
        values=values,
        unavailable_sources=unavailable_sources(snapshot, facts),
    )
    return vector, {name: merged.get(name) for name in SIGNALS if merged.get(name) is not None}
