"""Решение — чистая функция: decide(входы, политика) → итог. Без запросов наружу и без now().

Все входы (снимок заявки, признаки, агрегаты графа, итог скоринга, сигналы) собраны до вызова и
сохраняются в записи решения — повторный вызов на них даёт тот же итог (машина времени).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from node.modules.features.domain import FeatureVector
from node.modules.index.domain import GroupView
from node.modules.policy.domain import Channel, MandatoryCheck, Point, PolicyBundle, resolve_action
from node.modules.policy.reasons import LEVEL_ORDER, Level, Reason, max_level
from node.modules.scoring.domain import ScoringOutcome
from shared.contracts.application import ApplicationSnapshot, MandatoryChecks

STOP_BY_NORM = "stop_by_norm"

MANDATORY_CHECKS: dict[MandatoryCheck, Callable[[MandatoryChecks], bool]] = {
    "self_ban_active": lambda c: c.self_ban == "active",
    "bureau_blocked": lambda c: c.bureau in ("blocked", "busy"),
    "biometry_failed": lambda c: c.biometry == "failed",
    "phone_not_owned": lambda c: not c.phone_owner_match,
}


class DecisionInputs(BaseModel):
    model_config = ConfigDict(frozen=True)

    point: Point
    channel: Channel
    as_of: datetime
    application_version: int
    snapshot: ApplicationSnapshot
    features: FeatureVector
    graph: GroupView
    scoring: ScoringOutcome
    signals: dict[str, Any]


class DecisionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    outcome: Literal["assessed", "stopped_by_norm"]
    level: Level | None
    action: str
    reasons: list[Reason]
    valid_until: datetime


def _graph_reasons(inputs: DecisionInputs, bundle: PolicyBundle) -> list[Reason]:
    """Групповой флаг — только при двух и более независимых редких связях или всплеске (Блок 3)."""
    group, view = bundle.policy.group, inputs.graph
    links_flag = view.independent_rare_links >= group.min_independent_rare_links
    if not links_flag and not view.burst:
        return []
    roles = [r for r in view.shared_roles if r.role in group.red_when.shared_roles]
    red = view.independent_rare_links >= group.red_when.min_independent_rare_links or bool(roles)
    level: Level = "red" if red else "yellow"
    reasons: list[Reason] = []
    if links_flag:
        reasons.append(bundle.reason("GRAPH_RARE_SHARED_LINKS", [link.model_dump() for link in view.rare_links], level))
    if view.burst:
        reasons.append(
            bundle.reason(
                "GRAPH_GROUP_BURST",
                [
                    {
                        "group_applications": view.group_applications,
                        "recent_applications": view.recent_applications,
                        "background_per_window": view.background_per_window,
                    }
                ],
                level,
            )
        )
    if roles:
        reasons.append(bundle.reason("GRAPH_GROUP_SHARED_ROLE", [r.model_dump() for r in roles], level))
    return reasons


def _model_reasons(inputs: DecisionInputs, bundle: PolicyBundle) -> list[Reason]:
    """Жёлтый — калиброванная вероятность выше порога; красный — оценочная стоимость риска выше аппетита (ревью C)."""
    scoring, model = inputs.scoring, bundle.policy.model
    reasons: list[Reason] = []
    if scoring.status == "no_model" or scoring.missing_typologies:
        missing: dict[str, Any] = {
            "reason": scoring.reason,
            "checked_models": scoring.checked_models,
            "missing_typologies": scoring.missing_typologies,
        }
        reasons.append(bundle.reason("SYSTEM_NO_MODEL", [missing], None))
    if model is None:
        return reasons
    for score in scoring.scores:
        risk_cost = score.probability * inputs.snapshot.loan.amount * model.loss_given_fraud[inputs.channel]
        level: Level | None = None
        if risk_cost >= model.risk_appetite:
            level = "red"
        elif score.probability >= model.yellow_probability[score.typology]:
            level = "yellow"
        if level is None:
            continue
        evidence: dict[str, Any] = {
            "model_version_id": score.model_version_id,
            "probability": score.probability,
            "risk_cost_estimate": round(risk_cost),
            "risk_cost_is_estimate": True,
            "contributions": [c.model_dump(mode="json") for c in score.contributions],
        }
        reasons.append(bundle.reason(f"MODEL_{score.typology}_RISK", [evidence], level))
    return reasons


def _coordination_reasons(inputs: DecisionInputs, bundle: PolicyBundle) -> list[Reason]:
    """Группа координации (ревью E): роль заявки работает необычно часто против своего обычного темпа."""
    rules = bundle.policy.coordination
    flagged = [c for c in inputs.graph.coordination if c.flagged]
    if rules is None or not flagged:
        return []
    return [bundle.reason("GRAPH_COORDINATION_CLUSTER", [c.model_dump() for c in flagged], rules.level)]


def _source_reasons(inputs: DecisionInputs, bundle: PolicyBundle) -> list[Reason]:
    """Какие источники не ответили — видно в причинах; уровень это не поднимает (Блок 3)."""
    missing = inputs.features.unavailable_sources
    reasons = []
    if missing:
        reasons.append(bundle.reason("SYSTEM_SOURCE_UNAVAILABLE", [{"sources": missing}], None))
    if "inps" in missing:
        reasons.append(bundle.reason("SYSTEM_INCOME_NOT_CONFIRMED", [{"source": "inps"}], None))
    if inputs.snapshot.program is not None and inputs.features.values.get("price_comparables_level", 0) is None:
        reasons.append(bundle.reason("SYSTEM_PRICE_NOT_CHECKED", [{"item": inputs.snapshot.program.item_code}], None))
    return reasons


def decide(inputs: DecisionInputs, bundle: PolicyBundle) -> DecisionResult:
    policy = bundle.policy
    valid_until = inputs.as_of + policy.assessment_validity.for_channel(inputs.channel)

    stops = [
        bundle.reason(rule.code, [{"check": rule.check}], None)
        for rule in policy.mandatory_rules
        if MANDATORY_CHECKS[rule.check](inputs.snapshot.mandatory_checks)
    ]
    if stops:
        return DecisionResult(
            outcome="stopped_by_norm", level=None, action=STOP_BY_NORM, reasons=stops, valid_until=valid_until
        )

    reasons = [
        bundle.reason(rule.code, [{"signal": rule.signal, "value": inputs.signals[rule.signal]}], rule.min_level)
        for rule in policy.product_rules
        if inputs.signals.get(rule.signal)
    ]
    reasons += _model_reasons(inputs, bundle)
    reasons += _graph_reasons(inputs, bundle)
    reasons += _coordination_reasons(inputs, bundle)
    reasons += _source_reasons(inputs, bundle)

    level = max_level([r.level for r in reasons if r.level is not None])
    leading = max(
        (r for r in reasons if r.level is not None), key=lambda r: LEVEL_ORDER[r.level or "green"], default=None
    )
    return DecisionResult(
        outcome="assessed",
        level=level,
        action=resolve_action(policy, inputs.point, level, leading),
        reasons=reasons,
        valid_until=valid_until,
    )
