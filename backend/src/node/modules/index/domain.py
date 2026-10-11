"""Чистая логика модуля без ввода-вывода: атрибуты заявки, редкость связей, групповой флаг."""

import hashlib
import hmac
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field

from node.modules.policy.domain import CoordinationPolicy, GroupPolicy, IndexPolicy
from shared.contracts.application import ApplicationSnapshot
from shared.errors import ConfigurationError

APPLICANT = "applicant"


@dataclass(frozen=True)
class Attribute:
    kind: str
    role: str
    key: str
    display: str


def keyed(secret: bytes, kind: str, value: str) -> str:
    return hmac.new(secret, f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()


def subject_key(secret: bytes, pinfl: str) -> str:
    return keyed(secret, "pinfl", pinfl)


def _normalize_address(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _mask_tail(value: str, visible: int) -> str:
    return "•" * max(len(value) - visible, 0) + value[-visible:]


def _mask_head(value: str, visible: int) -> str:
    return value[:visible] + "…" if len(value) > visible else value


def extract(snapshot: ApplicationSnapshot, secret: bytes) -> list[Attribute]:
    """Все атрибуты снимка: идентичность заявителя, сам заявитель и роли (сотрудник, помощник, поставщик)."""
    a = snapshot.applicant
    raw: list[tuple[str, str, str, str]] = [
        ("pinfl", APPLICANT, a.pinfl, _mask_tail(a.pinfl, 4)),
        ("phone", APPLICANT, a.phone, _mask_tail(a.phone, 4)),
    ]
    if a.device_id:
        raw.append(("device", APPLICANT, a.device_id, _mask_head(a.device_id, 4)))
    if a.address:
        normalized = _normalize_address(a.address)
        raw.append(("address", APPLICANT, normalized, _mask_head(normalized, 12)))
    if a.employer_inn:
        raw.append(("employer", APPLICANT, a.employer_inn, _mask_tail(a.employer_inn, 3)))
    raw.append(("branch", "branch", snapshot.branch_id, snapshot.branch_id))
    if snapshot.employee_id:
        raw.append(("employee", "employee", snapshot.employee_id, snapshot.employee_id))
    if snapshot.program is not None:
        raw.append(("helper", "helper", snapshot.program.helper_id, snapshot.program.helper_id))
        raw.append(
            ("supplier", "supplier", snapshot.program.supplier_inn, _mask_tail(snapshot.program.supplier_inn, 3))
        )
    return [Attribute(kind, role, keyed(secret, kind, value), display) for kind, role, value, display in raw]


def window_start(as_of: datetime, policy: IndexPolicy) -> datetime:
    return as_of - timedelta(days=policy.window_days)


def hub_threshold(policy: IndexPolicy, kind: str) -> int:
    threshold = policy.hub_thresholds.get(kind)
    if threshold is None:
        raise ConfigurationError(f"Для атрибута {kind} не задан порог шумного хаба")
    return threshold


def is_rare_shared(policy: IndexPolicy, kind: str, subjects: int) -> bool:
    """Связь редкая и общая: атрибут есть хотя бы у двух разных людей и не у толпы."""
    return 2 <= subjects <= hub_threshold(policy, kind)


def link_weight(subjects: int) -> float:
    """Вес по редкости 1 / ln(n), как в мере Адамика–Адара."""
    return round(1.0 / math.log(subjects), 4)


class RareLink(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str
    display: str
    subjects: int
    weight: float


class SharedRole(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: str
    display: str
    applications: int


class CoordinationSignal(BaseModel):
    """Роль заявки (сотрудник, помощник, поставщик) и её темп: последние дни против сглаженного обычного."""

    model_config = ConfigDict(frozen=True)

    role: str
    display: str
    recent_applications: int
    pace_per_window: float
    ratio: float
    flagged: bool


class GroupView(BaseModel):
    """Агрегаты графа для записи решения: группа идентичности и сигналы группы координации (ревью E)."""

    model_config = ConfigDict(frozen=True)

    rare_links: list[RareLink]
    independent_rare_links: int
    group_applications: int
    group_subjects: int
    recent_applications: int
    background_per_window: float
    burst: bool
    shared_roles: list[SharedRole]
    coordination: list[CoordinationSignal] = Field(default_factory=list)
    member_subjects: tuple[str, ...] = Field(default=(), exclude=True)


class RoleConcentrations(BaseModel):
    """Сглаженные концентрации ролей программной заявки на момент as_of (m-оценка, ревью «оверинжиниринг»)."""

    model_config = ConfigDict(frozen=True)

    supplier_ratio: float | None = None
    branch_supplier_hhi: float | None = None
    employee_ratio: float | None = None
    helper_burst_ratio: float | None = None
    helper_supplier_share: float | None = None


def burst(
    policy: GroupPolicy, index: IndexPolicy, first_seen: list[datetime], as_of: datetime
) -> tuple[int, float, bool]:
    """Всплеск: заявок группы за окно против её же фона за остальную часть окна индекса."""
    recent, earlier = split_recent(first_seen, as_of, policy.burst.window_days, index.window_days)
    background_windows = (index.window_days - policy.burst.window_days) / policy.burst.window_days
    background = round(earlier / background_windows, 4) if background_windows > 0 else 0.0
    flagged = recent >= policy.burst.min_applications and recent >= policy.burst.min_ratio_to_background * background
    return recent, background, flagged


def independent_links(links: list[RareLink]) -> int:
    """Независимые редкие связи — по разным видам атрибутов: два телефона одной семьи — одна связь."""
    return len({link.kind for link in links})


def split_recent(times: list[datetime], as_of: datetime, recent_days: int, window_days: int) -> tuple[int, int]:
    """Сколько появлений за последние recent_days и сколько раньше в окне индекса."""
    recent_from = as_of - timedelta(days=recent_days)
    since = as_of - timedelta(days=window_days)
    recent = sum(1 for t in times if t > recent_from)
    earlier = sum(1 for t in times if since < t <= recent_from)
    return recent, earlier


def smoothed_share(count: int, total: int, prior: float, weight: float) -> float:
    """m-оценка доли: при малом total доля тянется к априорной."""
    return (count + weight * prior) / (total + weight)


def smoothed_pace(earlier: int, background_windows: float, prior_pace: float, prior_windows: float) -> float:
    """Обычный темп роли за окно: собственная история, сглаженная к среднему темпу ролей того же вида."""
    return (earlier + prior_windows * prior_pace) / (background_windows + prior_windows)


def pace_ratio(recent: int, pace: float) -> float:
    """Во сколько раз последнее окно выше обычного темпа; при нулевом темпе темп считается равным одной заявке."""
    return round(recent / pace, 4) if pace > 0 else float(recent)


def coordination_signal(
    policy: CoordinationPolicy,
    index: IndexPolicy,
    role: str,
    display: str,
    times: list[datetime],
    prior_pace: float,
    as_of: datetime,
) -> CoordinationSignal:
    recent, earlier = split_recent(times, as_of, policy.window_days, index.window_days)
    background_windows = (index.window_days - policy.window_days) / policy.window_days
    pace = smoothed_pace(earlier, background_windows, prior_pace, policy.prior_weight_windows)
    ratio = pace_ratio(recent, pace)
    return CoordinationSignal(
        role=role,
        display=display,
        recent_applications=recent,
        pace_per_window=round(pace, 4),
        ratio=ratio,
        flagged=recent >= policy.min_applications and ratio >= policy.min_ratio_to_pace,
    )
