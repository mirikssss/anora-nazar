"""Параметры генератора мира — модель файла `params/world-*.yaml`. Каждое число генератора приходит отсюда."""

from datetime import date
from pathlib import Path
from typing import Annotated, Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from shared.contracts.facts import IncidentKind

DEFAULT_PARAMS_PATH = Path(__file__).parent / "params" / "world-v1.yaml"

IdentityKind = Literal["phone", "device", "address"]
HOURS_PER_DAY = 24


def _ordered[T: float](bounds: tuple[T, T]) -> tuple[T, T]:
    if bounds[0] > bounds[1]:
        raise ValueError("Нижняя граница диапазона больше верхней")
    return bounds


IntRange = Annotated[tuple[int, int], AfterValidator(_ordered)]
FloatRange = Annotated[tuple[float, float], AfterValidator(_ordered)]
Probability = Annotated[float, Field(ge=0, le=1)]
Count = Annotated[int, Field(ge=0)]
Positive = Annotated[int, Field(ge=1)]


class _Params(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class LogNormal(_Params):
    """Логнормальное распределение: медиана и сигма логарифма."""

    median: float = Field(gt=0)
    sigma: float = Field(ge=0)


class BoundedLogNormal(LogNormal):
    min: int = Field(ge=1)
    max: int = Field(ge=1)


class Period(_Params):
    start: date
    months: Positive

    @model_validator(mode="after")
    def _month_start(self) -> Self:
        if self.start.day != 1:
            raise ValueError("Период начинается с первого числа месяца")
        return self


class Dormitories(_Params):
    count: Count
    residents: IntRange


class Population(_Params):
    people: Positive
    birth_years: IntRange
    household_sizes: dict[Positive, float] = Field(min_length=1)
    shared_phone_household_share: Probability
    shared_device_household_share: Probability
    dormitories: Dormitories
    card_in_bank_share: Probability
    inps_available_share: Probability
    inps_voluntary_distinguishable: bool
    monthly_income: LogNormal
    spending_to_income: LogNormal
    male_share: Probability
    phone_operator_codes: list[Annotated[str, Field(pattern=r"^\d{2}$")]] = Field(min_length=1)
    device_age_days: IntRange


class Employers(_Params):
    count: Positive
    size_zipf: float = Field(ge=0)
    new_share: Probability
    max_headcount: Positive
    headcount_growth: LogNormal


class PayrollProjects(_Params):
    count: Count
    wave_size: IntRange
    wave_days: Positive


class Region(_Params):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    districts: Positive


class Suppliers(_Params):
    count: Positive
    new_share: Probability
    headcount: IntRange


class CatalogItemParams(_Params):
    code: str = Field(min_length=1)
    category: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    median: float = Field(gt=0)
    sigma: float = Field(ge=0)
    quantity: IntRange


class ProgramBatches(_Params):
    share: Probability
    size: IntRange
    days: Positive


class RegistrationAge(_Params):
    established: IntRange
    new: IntRange


class Organizations(_Params):
    employers: Employers
    payroll_projects: PayrollProjects
    regions: list[Region] = Field(min_length=1)
    branches_per_region: Positive
    employees_per_branch: Positive
    helpers_per_district: Positive
    suppliers: Suppliers
    registration_age_days: RegistrationAge
    items: list[CatalogItemParams] = Field(min_length=1)
    normal_program_batches: ProgramBatches


class Lender(_Params):
    code: str = Field(min_length=1, pattern=r"^[A-Z]$")
    share: float = Field(gt=0)


class MandatoryFailures(_Params):
    self_ban_active: Probability
    bureau_busy: Probability
    biometry_failed: Probability
    phone_not_owned: Probability


class Applications(_Params):
    lender: str
    online_per_month: Count
    program_per_month: Count
    online_branch_id: str = Field(min_length=1)
    online_amount: BoundedLogNormal
    amount_step: Positive
    online_terms: list[Positive] = Field(min_length=1)
    program_terms: list[Positive] = Field(min_length=1)
    hour_weights: list[float] = Field(min_length=HOURS_PER_DAY, max_length=HOURS_PER_DAY)
    night_hours: list[Annotated[int, Field(ge=0, lt=HOURS_PER_DAY)]] = Field(min_length=1)
    second_version_share: Probability
    second_version_delay_minutes: IntRange
    second_version_amount_factor: FloatRange
    mandatory_failures: MandatoryFailures
    source_lead_minutes: IntRange

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.online_per_month + self.program_per_month == 0:
            raise ValueError("Нужна хотя бы одна заявка в месяц")
        if len(set(self.night_hours)) >= HOURS_PER_DAY:
            raise ValueError("Ночь не может занимать все сутки")
        if not all(self.hour_weights[hour] > 0 for hour in self.night_hours):
            raise ValueError("У ночных часов должен быть положительный вес")
        if not any(w > 0 for hour, w in enumerate(self.hour_weights) if hour not in self.night_hours):
            raise ValueError("У дневных часов должен быть положительный вес")
        return self


class SessionParams(_Params):
    access_recovery_hours: FloatRange
    new_device_age_days: IntRange
    remote_control_share: Probability
    form_seconds: IntRange
    fast_form_seconds: IntRange


class BureauParams(_Params):
    active_loans: IntRange
    closed_loans: IntRange
    self_ban_lifted_days: IntRange


class SourcesParams(_Params):
    card_months: Positive
    spending_monthly_sigma: float = Field(ge=0)
    inps_months: Positive
    inps_contribution_rate: float = Field(gt=0)
    inps_monthly_sigma: float = Field(ge=0)
    income_jump_months: Positive
    income_jump_factor: FloatRange


class SignalProbabilities(_Params):
    """Вероятности признаков сессии и бюро — общий профиль честных и жертв F1."""

    access_recovery_hours_before: Probability
    new_device_days: Probability
    remote_control_or_call: Probability
    night: Probability
    first_credit: Probability
    self_ban_lifted_30d: Probability
    pasted_fast_form: Probability
    amount_to_spending: LogNormal


class PremiumPrice(_Params):
    share: Probability
    markup: LogNormal


class Honest(SignalProbabilities):
    income_jump: Probability
    first_payment_missed: Probability
    premium_price: PremiumPrice
    young_supplier_share: Probability


class CoercionParams(SignalProbabilities):
    share_of_online: Probability
    victims_without_anomalies: Probability
    clean_history_share: Probability


class NetworkParams(_Params):
    share_of_applications: Probability
    ring_size: IntRange
    ring_days: Positive
    identity_kinds: list[IdentityKind] = Field(min_length=1)
    single_kind_rings: Probability
    coordination_rings: Probability
    coordination_shared_roles: IntRange
    shared_employee_share: Probability
    first_credit: Probability


class ProgramSchemeParams(_Params):
    share_of_program: Probability
    overpriced: Probability
    overprice: LogNormal
    new_supplier: Probability
    helper_burst: Probability
    burst_days: Positive
    spread_days: Positive
    outside_helper_mahalla: Probability
    income_jump: Probability
    scheme_size: IntRange


class Fraud(_Params):
    f1: CoercionParams
    f2: NetworkParams
    f3: ProgramSchemeParams


class ObservationDays(_Params):
    online: Positive
    program: Positive


class TypologyOutcome(_Params):
    detected: Probability
    delay_days: IntRange
    kinds: dict[IncidentKind, float] = Field(min_length=1)


class NetworkOutcome(TypologyOutcome):
    first_payment_missed_days: IntRange


class Outcomes(_Params):
    observation_days: ObservationDays
    payment_interval_days: Positive
    f1: TypologyOutcome
    f2: NetworkOutcome
    f3: TypologyOutcome
    false_alarm_share: Probability
    unconfirmed_complaint_share: Probability
    inps_correction_share: Probability
    inps_correction_delay_days: IntRange
    inps_correction_factor: FloatRange


class Naming(_Params):
    """Шаблоны текстов данных мира; поля подставляются через str.format."""

    district: str
    mahalla: str
    address: str
    dormitory: str
    branch: str
    employee: str
    employee_role: str
    supplier: str


class WorldParams(_Params):
    version: str = Field(min_length=1)
    seed: int
    scale: float = Field(gt=0)
    period: Period
    timezone: str
    population: Population
    organizations: Organizations
    lenders: list[Lender] = Field(min_length=1)
    applications: Applications
    session: SessionParams
    bureau: BureauParams
    sources: SourcesParams
    honest: Honest
    fraud: Fraud
    outcomes: Outcomes
    naming: Naming

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"Неизвестный часовой пояс {self.timezone}") from error
        codes = [lender.code for lender in self.lenders]
        if len(set(codes)) != len(codes):
            raise ValueError("Коды кредиторов повторяются")
        if self.applications.lender not in codes:
            raise ValueError("Кредитор узла не найден среди кредиторов")
        if self.fraud.f2.coordination_shared_roles[0] < 1:
            raise ValueError("У координационного кольца хотя бы одна общая роль")
        return self

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def lender_share(self, code: str) -> float:
        return next(lender.share for lender in self.lenders if lender.code == code)


def load_params(path: Path, scale: float | None = None) -> WorldParams:
    """Читает файл параметров; `scale` подменяет масштаб из файла (тесты берут малый мир)."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Файл параметров {path} — не словарь")
    if scale is not None:
        raw["scale"] = scale
    return WorldParams.model_validate(raw)
