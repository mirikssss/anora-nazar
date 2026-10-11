"""Чистая функция решения: одинаковые входы — одинаковый итог; уровни по правилам политики."""

from datetime import UTC, datetime

from node.modules.decisions.domain import DecisionInputs, decide
from node.modules.features.domain import from_group
from node.modules.index.domain import GroupView, RareLink, SharedRole
from node.modules.policy.service import PolicyRegistry
from node.modules.scoring.domain import ScoringOutcome
from node.settings import PACKAGE_DIR
from shared.contracts.application import ApplicationSnapshot

BUNDLE = PolicyRegistry.from_dir(PACKAGE_DIR / "modules" / "policy" / "rules", "policy-v1").active
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
        features=from_group(group),
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
