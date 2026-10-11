"""Политика как данные: разбор YAML и выбор действия. Без ввода-вывода."""

import copy
from datetime import timedelta
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from node.modules.policy.reasons import CatalogEntry, Level, Reason, ReasonSource, Typology
from shared.contracts.network import CounterName
from shared.errors import ConfigurationError

Point = Literal["T1", "T4"]
PointAny = Literal["T1", "T3", "T4"]
Channel = Literal["online", "program"]
MandatoryCheck = Literal["self_ban_active", "bureau_blocked", "biometry_failed", "phone_not_owned"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


Probability = Annotated[float, Field(gt=0, lt=1)]


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
    max_hops: int | None = Field(default=None, gt=0)  # None — без ограничения (policy-v1)


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


class CoordinationPolicy(_Frozen):
    """Группа координации (ревью E): концентрация роли во времени против её сглаженного обычного темпа."""

    roles: list[str]
    window_days: int = Field(gt=0)
    min_applications: int = Field(gt=0)
    min_ratio_to_pace: float = Field(gt=0)
    prior_weight_windows: float = Field(gt=0)
    level: Level | None


class ModelPolicy(_Frozen):
    """Источник «модель»: жёлтый — по калиброванной вероятности, красный — оценочная стоимость риска
    (вероятность × сумма × доля невозвратной потери) выше аппетита банка (ревью C)."""

    expected_typologies: dict[Point, list[Typology]]
    yellow_probability: dict[Typology, Probability]
    loss_given_fraud: dict[Channel, Probability]
    risk_appetite: int = Field(gt=0)
    top_contributions: int = Field(gt=0)


class TransferPolicy(_Frozen):
    """Т3: большая доля кредита в первые часы на новую карту, связанную с другими заёмщиками, — красный."""

    credit_share_min: float = Field(gt=0, le=1)
    within_hours: int = Field(gt=0)
    linked_borrowers_min: int = Field(gt=1)
    window_days: int = Field(gt=0)


class AcceptancePolicy(_Frozen):
    """Т5: пакет актов одного подписанта в один день или поставщик из стоп-листа — удержание оплаты."""

    batch_acts_per_signer_day: int = Field(gt=1)
    required_check: str


class NetworkRule(_Frozen):
    """Правило сети: счётчик ответа оператора не ниже порога — причина; level None — только улика."""

    code: str
    counter: CounterName
    min: int = Field(gt=0)
    level: Level | None


class NetworkPolicy(_Frozen):
    """Сеть кредиторов (Блок 2–4): выключена по умолчанию, включает риск-менеджер со вторым подписантом.

    Как и групповой флаг, одна общая связь уровень не поднимает: combined_min_rules и больше сработавших правил —
    независимые связи, уровень не ниже combined_level. Совпадение с подтверждённым делом другого кредитора —
    confirmed_level, но не автоматический отказ (Блок 4).
    """

    enabled: bool
    rules: list[NetworkRule]
    combined_min_rules: int = Field(gt=1)
    combined_level: Level
    confirmed_level: Level


class MandatoryRule(_Frozen):
    code: str
    check: MandatoryCheck


class ProductRule(_Frozen):
    code: str
    signal: str
    min_level: Level


class ActionRule(_Frozen):
    """sole_sources — правило действует, только если все причины с уровнем этой типологии и из этих источников.

    Так проверка намерения не закрывает независимые сильные основания (граф, сеть, правила продукта).
    """

    point: Point
    typology: Typology | None = None
    level: Level | None = None
    sole_sources: list[ReasonSource] | None = None
    action: str

    def covers(self, leveled: list[Reason]) -> bool:
        if self.sole_sources is None:
            return True
        return all(r.typology == self.typology and r.source in self.sole_sources for r in leveled)


class Actions(_Frozen):
    green: str
    rules: list[ActionRule]


class Policy(_Frozen):
    version: str
    reasons_version: str
    assessment_validity: AssessmentValidity
    index: IndexPolicy
    group: GroupPolicy
    coordination: CoordinationPolicy | None = None
    model: ModelPolicy | None = None
    transfers: TransferPolicy | None = None
    acceptance: AcceptancePolicy | None = None
    network: NetworkPolicy | None = None
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


def resolve_action(policy: Policy, point: Point, level: Level, leading: Reason | None, leveled: list[Reason]) -> str:
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
        if not rule.covers(leveled):
            continue
        return rule.action
    raise ConfigurationError(f"В политике {policy.version} нет действия для {point}, {leading.typology}, {level}")


def apply_changes(
    raw: dict[str, Any], changes: dict[str, bool | float], editable: list[str], version: str
) -> dict[str, Any]:
    """Новая версия из базовой: только разрешённые пути — числовые пороги и переключатели (сеть);
    результат проходит проверку схемы политики."""
    content = copy.deepcopy(raw)
    for path, value in changes.items():
        if path not in editable:
            raise ValueError(f"Порог {path} меняется только новой версией файла политики")
        *parents, leaf = path.split(".")
        node: Any = content
        for part in parents:
            node = node.get(part) if isinstance(node, dict) else None
            if node is None:
                raise ValueError(f"В политике нет раздела для {path}")
        current = node.get(leaf) if isinstance(node, dict) else None
        if isinstance(current, bool):
            if not isinstance(value, bool):
                raise ValueError(f"{path} — переключатель: true или false")
            node[leaf] = value
            continue
        if isinstance(value, bool) or not isinstance(current, int | float):
            raise ValueError(f"{path} — не числовой порог")
        node[leaf] = type(current)(value) if isinstance(current, int) and float(value).is_integer() else value
    content["version"] = version
    Policy.model_validate(content)
    return content
