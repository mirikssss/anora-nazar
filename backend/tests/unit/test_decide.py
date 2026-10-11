"""Чистая функция решения: одинаковые входы — одинаковый итог; уровни по правилам политики."""

from datetime import UTC, datetime, timedelta

from node.modules.consortium.domain import NetworkObservation
from node.modules.decisions.domain import (
    DecisionInputs,
    EarlierTransfer,
    TransferInputs,
    decide,
    recommend_transfer,
)
from node.modules.features.domain import FeatureVector, zone2_features
from node.modules.index.domain import GroupView, RareLink, SharedRole
from node.modules.policy.service import PolicyRegistry
from node.modules.scoring.domain import ModelScore, ScoringOutcome
from node.settings import PACKAGE_DIR
from shared.contracts.application import ApplicationSnapshot
from shared.contracts.network import ConfirmedMatch
from shared.contracts.transfers import TransferRecommendationIn

REGISTRY = PolicyRegistry.from_dir(PACKAGE_DIR / "modules" / "policy" / "rules", "policy-v1")
BUNDLE = REGISTRY.active
V2 = REGISTRY.get("policy-v2")
AS_OF = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
NO_MODEL = ScoringOutcome(status="no_model", reason="registry_empty", checked_models=[], scores=[])


def snapshot(**checks: object) -> ApplicationSnapshot:
    base = {"self_ban": "none", "bureau": "free", "biometry": "passed", "phone_owner_match": True}
    return ApplicationSnapshot.model_validate(
        {
            "channel": "online",
            "branch_id": "BR-01",
            "applicant": {"pinfl": "30000000000001", "phone": "998900000001"},
            "loan": {"amount": 1000, "term_months": 12},
            "disbursement_account": "ACC",
            "mandatory_checks": {**base, **checks},
        }
    )


def view(kinds: list[str], *, burst: bool = False, roles: list[str] | None = None) -> GroupView:
    return GroupView(
        rare_links=[RareLink(kind=k, display="•", subjects=2, weight=1.4427) for k in kinds],
        independent_rare_links=len(set(kinds)),
        group_applications=2,
        group_subjects=2,
        recent_applications=5 if burst else 2,
        background_per_window=0.0,
        burst=burst,
        shared_roles=[SharedRole(role=r, display=r, applications=2) for r in roles or []],
    )


def inputs(group: GroupView, **checks: object) -> DecisionInputs:
    return DecisionInputs(
        point="T1",
        channel="online",
        as_of=AS_OF,
        application_version=1,
        snapshot=snapshot(**checks),
        features=FeatureVector(set_version="fs-2", point="T1", values=zone2_features(group, None)),
        graph=group,
        scoring=NO_MODEL,
        signals={},
    )


def test_same_inputs_same_result() -> None:
    first = decide(inputs(view(["phone", "device"])), BUNDLE)
    assert decide(inputs(view(["phone", "device"])), BUNDLE) == first


def test_levels_follow_the_group_policy() -> None:
    assert decide(inputs(view([])), BUNDLE).level == "green"
    assert decide(inputs(view(["phone"])), BUNDLE).level == "green"
    assert decide(inputs(view(["phone", "phone"])), BUNDLE).level == "green"
    assert decide(inputs(view(["phone", "device"])), BUNDLE).level == "yellow"
    assert decide(inputs(view(["phone", "device", "address"])), BUNDLE).level == "red"
    assert decide(inputs(view(["phone", "device"], roles=["employee"])), BUNDLE).level == "red"
    assert decide(inputs(view([], burst=True)), BUNDLE).level == "yellow"


def test_group_reasons_lead_to_internal_review_never_to_refusal() -> None:
    result = decide(inputs(view(["phone", "device"])), BUNDLE)
    assert result.action == "internal_review"
    assert result.outcome == "assessed"


def test_validity_depends_on_channel() -> None:
    assert decide(inputs(view([])), BUNDLE).valid_until == AS_OF.replace(day=12)


def test_mandatory_rules_stop_before_anything_else() -> None:
    result = decide(inputs(view(["phone", "device", "address"]), bureau="busy", biometry="failed"), BUNDLE)
    assert result.outcome == "stopped_by_norm"
    assert [r.code for r in result.reasons] == ["MANDATORY_BUREAU_BLOCKED", "MANDATORY_BIOMETRY_FAILED"]


def scored(probability: float, amount: int) -> DecisionInputs:
    score = ModelScore(model_version_id="m", name="f1-t1", typology="F1", probability=probability, contributions=[])
    base = inputs(view([]))
    snap = base.snapshot.model_copy(update={"loan": base.snapshot.loan.model_copy(update={"amount": amount})})
    outcome = ScoringOutcome(
        status="scored", reason="partial", checked_models=["m"], scores=[score], missing_typologies=["F2"]
    )
    return base.model_copy(update={"scoring": outcome, "snapshot": snap})


def test_model_level_by_probability_and_estimated_risk_cost() -> None:
    model = V2.policy.model
    assert model is not None
    yellow_p = model.yellow_probability["F1"]
    small = int(model.risk_appetite / model.loss_given_fraud["online"] / 2)
    assert decide(scored(yellow_p / 2, small), V2).level == "green"
    assert decide(scored(yellow_p, small), V2).level == "yellow"
    red = decide(scored(yellow_p, int(model.risk_appetite / yellow_p / model.loss_given_fraud["online"]) + 1), V2)
    assert red.level == "red"
    reason = next(r for r in red.reasons if r.code == "MODEL_F1_RISK")
    assert reason.evidence[0]["risk_cost_is_estimate"] is True
    assert any(r.code == "SYSTEM_NO_MODEL" for r in red.reasons), "нет F2 — это видно в причинах"


V4 = REGISTRY.get("policy-v4")


def networked(counters: dict[str, int], confirmed: list[dict[str, str]] | None = None) -> DecisionInputs:
    observation = NetworkObservation(
        status="ok",
        as_of=AS_OF,
        counters=counters,  # type: ignore[arg-type]
        confirmed=[ConfirmedMatch.model_validate(m) for m in confirmed or []],
    )
    return inputs(view([])).model_copy(update={"network": observation})


def test_network_one_shared_link_is_evidence_two_raise_the_level() -> None:
    """Как групповой флаг: один общий телефон у чужих людей — улика (семьи), телефон и устройство — жёлтый."""
    phone = decide(networked({"phone_people_30d": 2}), V4)
    assert phone.level == "green"
    assert [(r.code, r.level) for r in phone.reasons if r.source == "network"] == [("NETWORK_SHARED_PHONE", None)]
    both = decide(networked({"phone_people_30d": 2, "device_people_30d": 3}), V4)
    assert both.level == "yellow"
    assert decide(networked({"pinfl_lenders_1h": 2}), V4).level == "yellow"
    confirmed = decide(networked({}, [{"kind": "phone", "typology": "F2", "confirmation": "confirmed_fraud"}]), V4)
    assert confirmed.level == "red" and confirmed.outcome == "assessed", "красный — проверка, не отказ"


def test_network_down_is_visible_and_does_not_raise_the_level() -> None:
    down = inputs(view([])).model_copy(
        update={"network": NetworkObservation(status="unavailable", as_of=AS_OF, error="upstream_unavailable")}
    )
    result = decide(down, V4)
    assert result.level == "green"
    assert [r.code for r in result.reasons if r.source == "network"] == ["SYSTEM_NETWORK_UNAVAILABLE"]


def test_intent_check_does_not_cover_independent_grounds() -> None:
    """Проверка намерения — только для сигналов модели F1; серия по ПИНФЛ в сети — звонок аналитика."""
    model = V4.policy.model
    assert model is not None
    small = int(model.risk_appetite / model.loss_given_fraud["online"] / 2)
    alone = scored(model.yellow_probability["F1"], small)
    assert decide(alone, V4).action == "intent_check"
    series = NetworkObservation(status="ok", as_of=AS_OF, counters={"pinfl_lenders_1h": 2})
    with_network = alone.model_copy(update={"network": series})
    assert decide(with_network, V4).action == "pause_for_call"
    assert decide(with_network, V2).action == "intent_check", "старые версии политики воспроизводятся как были"


def transfer(amount: int, minutes: int, transfer_id: str = "TR-2") -> TransferRecommendationIn:
    return TransferRecommendationIn(
        application_id="APP-1",
        transfer_id=transfer_id,
        amount=amount,
        recipient_card="8600000000000001",
        recipient_is_new=True,
        balance_before_credit=0,
        credited_at=AS_OF,
        requested_at=AS_OF + timedelta(minutes=minutes),
    )


def test_split_transfers_are_counted_together_and_network_links_the_card() -> None:
    earlier = [EarlierTransfer(transfer_id="TR-1", amount=300, requested_at=AS_OF + timedelta(minutes=10))]
    base = TransferInputs(
        as_of=AS_OF,
        application_version=1,
        loan_amount=1000,
        transfer=transfer(300, 20),
        recipient_borrowers=0,
        stop_matches=[],
    )
    assert recommend_transfer(base, V4).level == "green", "30 % — ниже порога доли"
    split = base.model_copy(update={"earlier_transfers": earlier})
    assert recommend_transfer(split, V4).level == "yellow", "два перевода по 30 % — 60 % кредита"
    card = NetworkObservation(status="ok", as_of=AS_OF, counters={"card_borrowers_30d": 2, "card_lenders_30d": 2})
    linked = split.model_copy(update={"network": card})
    result = recommend_transfer(linked, V4)
    assert (result.level, result.recommended_action) == ("red", "hold_until_confirmed")
    without = split.model_copy(update={"network": NetworkObservation(status="unavailable", as_of=AS_OF)})
    assert recommend_transfer(without, V4).level == "yellow", "без сети — по своим данным"
