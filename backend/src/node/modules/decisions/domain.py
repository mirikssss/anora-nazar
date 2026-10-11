"""Решение — чистая функция: decide(входы, политика) → итог. Без запросов наружу и без now().

Все входы (снимок заявки, признаки, агрегаты графа, итог скоринга, сигналы) собраны до вызова и
сохраняются в записи решения — повторный вызов на них даёт тот же итог (машина времени).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from node.modules.consortium.domain import NetworkObservation
from node.modules.features.domain import FeatureVector
from node.modules.index.domain import GroupView
from node.modules.policy.domain import Channel, MandatoryCheck, Point, PolicyBundle, resolve_action
from node.modules.policy.reasons import LEVEL_ORDER, Level, Reason, max_level
from node.modules.scoring.domain import ScoringOutcome
from shared.contracts.application import ApplicationSnapshot, MandatoryChecks
from shared.contracts.transfers import RecommendedAction, TransferRecommendationIn
from shared.errors import ConfigurationError

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
    network: NetworkObservation | None = None  # None — записи до сети (И1–И3)


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


def _network_reasons(inputs: DecisionInputs, bundle: PolicyBundle) -> list[Reason]:
    """Сеть видит то, чего не видит один банк. Не ответила — причина без уровня, решение по своим признакам."""
    rules, observation = bundle.policy.network, inputs.network
    if rules is None or observation is None or observation.status == "disabled":
        return []
    if observation.status == "unavailable":
        return [bundle.reason("SYSTEM_NETWORK_UNAVAILABLE", [{"error": observation.error}], None)]
    fired = [r for r in rules.rules if observation.counters.get(r.counter, 0) >= r.min]
    combined = len(fired) >= rules.combined_min_rules
    reasons = [
        bundle.reason(
            r.code,
            [{"counter": r.counter, "value": observation.counters.get(r.counter, 0), "threshold": r.min}],
            max_level([lvl for lvl in (r.level, rules.combined_level if combined else None) if lvl is not None])
            if r.level is not None or combined
            else None,
        )
        for r in fired
    ]
    if observation.confirmed:
        evidence = [m.model_dump() for m in observation.confirmed]
        reasons.append(bundle.reason("NETWORK_CONFIRMED_CASE_IDENTIFIER", evidence, rules.confirmed_level))
    return reasons


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
    reasons += _network_reasons(inputs, bundle)
    reasons += _source_reasons(inputs, bundle)

    leveled = [r for r in reasons if r.level is not None]
    level = max_level([r.level for r in leveled if r.level is not None])
    leading = max(leveled, key=lambda r: LEVEL_ORDER[r.level or "green"], default=None)
    return DecisionResult(
        outcome="assessed",
        level=level,
        action=resolve_action(policy, inputs.point, level, leading, leveled),
        reasons=reasons,
        valid_until=valid_until,
    )


class EarlierTransfer(BaseModel):
    model_config = ConfigDict(frozen=True)

    transfer_id: str
    amount: int
    requested_at: datetime


class TransferInputs(BaseModel):
    """Входы рекомендации Т3 — собраны до вызова и хранятся в записи решения."""

    model_config = ConfigDict(frozen=True)

    as_of: datetime
    application_version: int
    loan_amount: int
    transfer: TransferRecommendationIn
    recipient_borrowers: int
    stop_matches: list[dict[str, Any]]
    earlier_transfers: list[EarlierTransfer] = []  # дробление: прошлые переводы этого кредита в окне
    network: NetworkObservation | None = None


class TransferRecommendation(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: Level
    recommended_action: RecommendedAction
    reasons: list[Reason]


def recommend_transfer(inputs: TransferInputs, bundle: PolicyBundle) -> TransferRecommendation:
    """Т3: большая доля кредита в первые часы на новую карту, связанную с другими заёмщиками или с делом, —
    красный и совет удержать до подтверждения; решает транзакционный антифрод банка (ревью A).

    Доля считается по всем переводам этого кредита в окне — дробление суммы её не прячет. Заёмщики с этой
    картой — свои по индексу плюс у других кредиторов по сети, если она включена и ответила.
    """
    rules = bundle.policy.transfers
    if rules is None:
        raise ConfigurationError(f"В политике {bundle.policy.version} нет правил первого перевода")
    t = inputs.transfer
    window_start = t.credited_at
    earlier = [e for e in inputs.earlier_transfers if window_start <= e.requested_at <= t.requested_at]
    moved = t.amount + sum(e.amount for e in earlier)
    share = round(max(0, moved - t.balance_before_credit) / inputs.loan_amount, 4)
    hours = round((t.requested_at - t.credited_at).total_seconds() / 3600, 2)
    early_big = share >= rules.credit_share_min and hours <= rules.within_hours
    network = inputs.network if inputs.network is not None and inputs.network.status == "ok" else None
    network_borrowers = network.counters.get("card_borrowers_30d", 0) if network is not None else 0
    linked_borrowers = inputs.recipient_borrowers + network_borrowers
    linked = linked_borrowers >= rules.linked_borrowers_min
    confirmed = [m for m in network.confirmed if m.kind == "card"] if network is not None else []
    red = bool(inputs.stop_matches) or bool(confirmed) or (early_big and t.recipient_is_new and linked)
    level: Level = "red" if red else "yellow" if early_big and t.recipient_is_new else "green"
    reasons = []
    if early_big:
        evidence: dict[str, Any] = {
            "credit_share": share,
            "hours_since_credit": hours,
            "threshold": rules.credit_share_min,
            "transfers_counted": len(earlier) + 1,
        }
        reasons.append(bundle.reason("F1_FIRST_TRANSFER_CREDIT_SHARE", [evidence], level))
    if t.recipient_is_new:
        evidence = {
            "recipient_borrowers": inputs.recipient_borrowers,
            "network_borrowers": network_borrowers if network is not None else None,
            "network_lenders": network.counters.get("card_lenders_30d", 0) if network is not None else None,
            "threshold": rules.linked_borrowers_min,
        }
        reasons.append(bundle.reason("F1_NEW_RECIPIENT", [evidence], level if early_big else None))
    if inputs.stop_matches:
        reasons.append(bundle.reason("PRODUCT_CONFIRMED_CASE_IDENTIFIER", inputs.stop_matches, "red"))
    if confirmed:
        reasons.append(bundle.reason("NETWORK_CONFIRMED_CASE_IDENTIFIER", [m.model_dump() for m in confirmed], "red"))
    if inputs.network is not None and inputs.network.status == "unavailable":
        reasons.append(bundle.reason("SYSTEM_NETWORK_UNAVAILABLE", [{"error": inputs.network.error}], None))
    return TransferRecommendation(
        level=level, recommended_action="hold_until_confirmed" if red else "allow", reasons=reasons
    )
