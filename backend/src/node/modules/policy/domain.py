"""Политика как данные: разбор YAML и выбор действия. Без ввода-вывода."""

from datetime import timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from node.modules.policy.reasons import CatalogEntry, Level, Reason, Typology
from shared.errors import ConfigurationError

Point = Literal["T1", "T4"]
Channel = Literal["online", "program"]
MandatoryCheck = Literal["self_ban_active", "bureau_blocked", "biometry_failed", "phone_not_owned"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Duration(_Frozen):
    days: int = Field(default=0, ge=0)
    hours: int = Field(default=0, ge=0)

    def as_timedelta(self) -> timedelta:
        return timedelta(days=self.days, hours=self.hours)


class AssessmentValidity(_Frozen):
    online: Duration
    program: Duration

    def for_channel(self, channel: Channel) -> timedelta:
        return (self.online if channel == "online" else self.program).as_timedelta()


class IndexPolicy(_Frozen):
    window_days: int = Field(gt=0)
    identity_kinds: list[str]
    hub_thresholds: dict[str, int]
    marking_kinds: list[str]


class BurstPolicy(_Frozen):
    window_days: int = Field(gt=0)
    min_applications: int = Field(gt=0)
    min_ratio_to_background: float = Field(gt=0)


class GroupRedWhen(_Frozen):
    min_independent_rare_links: int = Field(gt=0)
    shared_roles: list[str]


class GroupPolicy(_Frozen):
    min_independent_rare_links: int = Field(gt=0)
    burst: BurstPolicy
    red_when: GroupRedWhen


class MandatoryRule(_Frozen):
    code: str
    check: MandatoryCheck


class ProductRule(_Frozen):
    code: str
    signal: str
    min_level: Level


class ActionRule(_Frozen):
    point: Point
    typology: Typology | None = None
    level: Level | None = None
    action: str


class Actions(_Frozen):
    green: str
    rules: list[ActionRule]


class Policy(_Frozen):
    version: str
    reasons_version: str
    assessment_validity: AssessmentValidity
    index: IndexPolicy
    group: GroupPolicy
    mandatory_rules: list[MandatoryRule]
    product_rules: list[ProductRule]
    actions: Actions


class PolicyBundle(_Frozen):
    """Политика вместе с каталогом причин и хешами исходных файлов — то, что попадает в запись решения."""

    policy: Policy
    catalog: dict[str, CatalogEntry]
    policy_hash: str
    catalog_version: str
    catalog_hash: str

    def reason(self, code: str, evidence: list[dict[str, Any]], level: Level | None) -> Reason:
        entry = self.catalog.get(code)
        if entry is None:
            raise ConfigurationError(f"Код причины {code} не описан в каталоге {self.catalog_version}")
        return Reason(
            code=code, typology=entry.typology, source=entry.source, evidence=evidence, norm=entry.norm, level=level
        )


def resolve_action(policy: Policy, point: Point, level: Level, leading: Reason | None) -> str:
    """Зелёный — обычный путь. Иначе действие задаёт ведущая причина: самый высокий уровень, затем порядок."""
    if level == "green" or leading is None:
        return policy.actions.green
    for rule in policy.actions.rules:
        if rule.point != point:
            continue
        if rule.typology is not None and rule.typology != leading.typology:
            continue
        if rule.level is not None and rule.level != level:
            continue
        return rule.action
    raise ConfigurationError(f"В политике {policy.version} нет действия для {point}, {leading.typology}, {level}")
