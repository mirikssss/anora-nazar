"""Чистая логика модуля без ввода-вывода: атрибуты заявки, редкость связей, групповой флаг."""

import hashlib
import hmac
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict

from node.modules.policy.domain import GroupPolicy, IndexPolicy
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


class GroupView(BaseModel):
    """Агрегаты графа для записи решения."""

    model_config = ConfigDict(frozen=True)

    rare_links: list[RareLink]
    independent_rare_links: int
    group_applications: int
    group_subjects: int
    recent_applications: int
    background_per_window: float
    burst: bool
    shared_roles: list[SharedRole]


def burst(
    policy: GroupPolicy, index: IndexPolicy, first_seen: list[datetime], as_of: datetime
) -> tuple[int, float, bool]:
    """Всплеск: заявок группы за окно против её же фона за остальную часть окна индекса."""
    recent_from = as_of - timedelta(days=policy.burst.window_days)
    since = window_start(as_of, index)
    recent = sum(1 for t in first_seen if t > recent_from)
    earlier = sum(1 for t in first_seen if since < t <= recent_from)
    background_windows = (index.window_days - policy.burst.window_days) / policy.burst.window_days
    background = round(earlier / background_windows, 4) if background_windows > 0 else 0.0
    flagged = recent >= policy.burst.min_applications and recent >= policy.burst.min_ratio_to_background * background
    return recent, background, flagged


def independent_links(links: list[RareLink]) -> int:
    """Независимые редкие связи — по разным видам атрибутов: два телефона одной семьи — одна связь."""
    return len({link.kind for link in links})
