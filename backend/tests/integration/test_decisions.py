"""Решения: режим «без модели», обязательные правила, удержания, неизменяемость, воспроизведение."""

import pytest
from sqlalchemy.exc import DBAPIError

from tests.integration.conftest import Node, online


def test_no_model_mode_is_explicit(node: Node) -> None:
    realm = node.new_sandbox()
    decision = node.assess(realm, "A", online("32000000000001", "998903330001"))
    assert decision["level"] == "green"
    no_model = [r for r in decision["reasons"] if r["code"] == "SYSTEM_NO_MODEL"]
    assert no_model and no_model[0]["evidence"][0]["reason"] == "registry_empty"
    assert no_model[0]["level"] is None


def test_mandatory_rule_stops_by_norm_without_level_or_hold(node: Node) -> None:
    realm = node.new_sandbox()
    snap = online("32000000000002", "998903330002", self_ban="active")
    decision = node.assess(realm, "A", snap)
    assert decision["outcome"] == "stopped_by_norm"
    assert decision["level"] is None
    assert decision["holds"] == []
    assert decision["reasons"][0] == {
        "code": "MANDATORY_SELF_BAN",
        "typology": None,
        "source": "rule",
        "evidence": [{"check": "self_ban_active"}],
        "norm": "п. 18",
        "level": None,
    }
    assert node.permit(realm, "A", snap).json()["refusal"]["code"] == "stopped_by_norm"


def test_three_independent_rare_links_give_red_and_a_hold(node: Node) -> None:
    realm = node.new_sandbox()
    common = {"device": "dev-ring", "address": "махалля Навбахор, дом 7"}
    node.assess(realm, "A", online("32000000000003", "998903330003", **common))
    decision = node.assess(realm, "B", online("32000000000004", "998903330003", **common))
    assert decision["level"] == "red"
    links = decision["reasons"][1]["evidence"]
    assert {link["kind"] for link in links} == {"phone", "device", "address"}
    assert all(link["subjects"] == 2 for link in links)
    assert decision["holds"][0]["required_check"] == "internal_review"


def test_burst_of_linked_applications_through_one_employee_is_red(node: Node) -> None:
    """Двенадцать заявок за день с одним адресом через одного сотрудника: всплеск и общая роль."""
    realm = node.new_sandbox()
    for i in range(11):
        node.assess(realm, f"H{i}", online(f"32000000002{i:03d}", f"99890334{i:04d}", address="ЖК Центр 1"))
    decision = node.assess(realm, "X", online("32000000000299", "998903349999", address="ЖК Центр 1"))
    assert decision["level"] == "red"
    assert {r["code"] for r in decision["reasons"]} >= {"GRAPH_GROUP_BURST", "GRAPH_GROUP_SHARED_ROLE"}


def test_decision_record_is_immutable_and_replays_identically(node: Node) -> None:
    realm = node.new_sandbox()
    decision = node.assess(realm, "A", online("32000000000005", "998903330005"))
    staff = node.staff(realm, "analyst-1")
    replay = node.client.get(f"/v1/decisions/{decision['decision_id']}/replay", headers=staff).json()
    assert replay["identical"] is True
    assert replay["policy_unchanged"] is True
    with pytest.raises(DBAPIError, match="immutable"):
        node.sql("UPDATE decisions SET level = 'red'")


def test_point_must_match_channel(node: Node) -> None:
    realm = node.new_sandbox()
    response = node.post(
        "conveyor",
        "/v1/assessments",
        realm,
        idem="k",
        json={
            "point": "T4",
            "application_id": "A",
            "application_version": 1,
            "occurred_at": node.clock.now().isoformat(),
            "snapshot": online("32000000000006", "998903330006"),
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "point_channel_mismatch"


def test_rights_are_enforced(node: Node) -> None:
    realm = node.new_sandbox()
    decision = node.assess(realm, "A", online("32000000000007", "998903330007"))
    wrong_scope = node.post("events", "/v1/assessments", realm, idem="k", json={})
    assert wrong_scope.status_code == 403
    control = node.staff(realm, "control-1")
    assert node.client.get("/v1/audit/verify", headers=control).status_code == 403
    analyst = node.staff(realm, "analyst-1")
    assert node.client.get(f"/v1/decisions/{decision['decision_id']}", headers=analyst).status_code == 200
