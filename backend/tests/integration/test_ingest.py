"""Приём событий: повторы, порядок версий, пропуски и запрос снимка у владельца."""

from datetime import timedelta

from tests.integration.conftest import Node, online

PHONE = "998902220000"


def _version_payload(snapshot: dict[str, object]) -> dict[str, object]:
    return {"snapshot": snapshot}


def test_duplicate_event_is_dropped(node: Node) -> None:
    realm = node.new_sandbox()
    snap = online("31000000000001", PHONE)
    node.assess(realm, "A", snap)
    body = {
        "event_id": "6f3c2a3e-1111-4c4c-9a9a-000000000001",
        "source": "bank-sim.sessions",
        "type": "session.new_device",
        "entity_type": "session_event",
        "entity_id": "s-1",
        "entity_version": None,
        "occurred_at": node.clock.now().isoformat(),
        "schema_version": 1,
        "payload": {"subject_pinfl": "31000000000001"},
    }
    first = node.post("events", "/v1/events", realm, json=body).json()
    second = node.post("events", "/v1/events", realm, json=body).json()
    assert first["outcome"] == "stored"
    assert second["outcome"] == "duplicate"
    assert node.sql("SELECT needs_reassessment FROM applications WHERE external_id = 'A'")[0][0] is True


def test_versions_apply_in_order_and_gaps_hold_money(node: Node) -> None:
    realm = node.new_sandbox()
    v1 = online("31000000000002", PHONE, amount=10_000_000)
    node.assess(realm, "A", v1)
    v3 = {**v1, "loan": {"amount": 12_000_000, "term_months": 12}}
    assert node.event(realm, "A", 3, payload=_version_payload(v3))["outcome"] == "parked"
    assert node.permit(realm, "A", v1).json()["refusal"]["code"] == "version_gap"

    v2 = {**v1, "loan": {"amount": 11_000_000, "term_months": 12}}
    assert node.event(realm, "A", 2, payload=_version_payload(v2))["outcome"] == "applied"
    row = node.sql("SELECT current_version, version_gap_since FROM applications WHERE external_id = 'A'")[0]
    assert row == (3, None)
    assert node.event(realm, "A", 1, payload=_version_payload(v1))["outcome"] == "stale"
    assert node.permit(realm, "A", v3, version=3).json()["refusal"]["code"] == "assessment_required"


def test_missing_version_is_requested_from_the_owner_after_timeout(node: Node) -> None:
    realm = node.new_sandbox()
    v1 = online("31000000000003", PHONE)
    node.assess(realm, "A", v1)
    v5 = {**v1, "loan": {"amount": 31_000_000, "term_months": 12}}
    node.event(realm, "A", 5, payload=_version_payload(v5))
    node.bank.snapshots["A"] = {"version": 5, "snapshot": v5}

    node.clock.set(node.clock.now() + timedelta(seconds=30))
    node.tasks.resolve_version_gaps()
    assert node.sql("SELECT current_version FROM applications WHERE external_id = 'A'")[0][0] == 1

    node.clock.set(node.clock.now() + timedelta(seconds=31))
    node.tasks.resolve_version_gaps()
    row = node.sql("SELECT current_version, version_gap_since FROM applications WHERE external_id = 'A'")[0]
    assert row == (5, None)


def test_cancelled_application_gets_no_permit(node: Node) -> None:
    realm = node.new_sandbox()
    snap = online("31000000000004", PHONE)
    node.assess(realm, "A", snap)
    assert node.event(realm, "A", None, type_="application.cancelled")["outcome"] == "applied"
    assert node.permit(realm, "A", snap).json()["refusal"]["code"] == "application_cancelled"
