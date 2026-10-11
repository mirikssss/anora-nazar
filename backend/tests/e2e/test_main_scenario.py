"""Главный сценарий: живой отзыв по индексу связей. Уровень связанной заявки — жёлтый или красный: красный даёт
оценочная стоимость риска модели, если модели выпущены в общий мир."""

import time

from tests.e2e.conftest import Sandbox, online_draft

PHONE = "998901112233"
DEVICE = "device-shared-001"


def test_live_revocation_by_linked_application(sandbox: Sandbox) -> None:
    a = sandbox.apply(online_draft("31111111111111", PHONE, device=DEVICE))
    assert a["last_decision"]["level"] == "green"
    assert a["last_decision"]["action"] == "continue"

    b = sandbox.apply(online_draft("32222222222222", PHONE, branch="BR-02", employee="EMP-02-1", device=DEVICE))
    assert b["last_decision"]["level"] in ("yellow", "red")
    assert b["last_decision"]["action"] == "internal_review"
    assert a["id"] in b["last_decision"]["marked_applications"]

    refused = sandbox.execute(a["id"])
    assert refused["status"] == "refused"
    assert refused["refusal"]["code"] == "reassessment_required"
    assert refused["refusal"]["details"]["cause"]["trigger_application"] == b["id"]

    reassessed = sandbox.reassess(a["id"])
    assert reassessed["last_decision"]["level"] in ("yellow", "red")
    codes = {r["code"] for r in reassessed["last_decision"]["reasons"]}
    assert "GRAPH_RARE_SHARED_LINKS" in codes

    held = sandbox.execute(a["id"])
    assert held["status"] == "refused"
    assert held["refusal"]["code"] == "active_hold"

    view = sandbox.node.get(f"/v1/applications/{a['id']}", headers=sandbox.as_staff("analyst-1")).json()
    assert view["holds"][0]["required_check"] == "internal_review"
    assert "GRAPH_RARE_SHARED_LINKS" in {basis["code"] for basis in view["holds"][0]["basis"]}


def test_control_branch_normal_link_keeps_level(sandbox: Sandbox) -> None:
    employer = "301234567"
    a = sandbox.apply(online_draft("33333333333333", "998902223344", employer=employer))
    assert a["last_decision"]["level"] == "green"

    c = sandbox.apply(
        online_draft("34444444444444", "998903334455", branch="BR-02", employee="EMP-02-1", employer=employer)
    )
    assert c["last_decision"]["level"] == "green"
    assert a["id"] in c["last_decision"]["marked_applications"]

    assert sandbox.execute(a["id"])["refusal"]["code"] == "reassessment_required"
    assert sandbox.reassess(a["id"])["last_decision"]["level"] == "green"
    executed = sandbox.execute(a["id"])
    assert executed["status"] == "executed"
    assert executed["outcome_reported"] is True


def test_failure_buttons(sandbox: Sandbox) -> None:
    a = sandbox.apply(online_draft("35555555555555", "998904445566"))
    b = sandbox.apply(online_draft("39999999999999", "998908889900"))
    flags = {"lose_outcome": True}
    sandbox.bank.patch("/v1/failures", json=flags, headers=sandbox.headers).raise_for_status()
    lost = sandbox.execute(a["id"])
    assert lost["status"] == "executed"
    assert lost["outcome_reported"] is False

    repeat = sandbox.bank.post(
        "/v1/failures/repeat-with-other-amount",
        headers=sandbox.headers,
        json={"operation_key": lost["operation_key"], "amount": lost["amount"] + 1},
    ).json()
    assert repeat["node_status_code"] == 409
    assert repeat["node_response"]["error"]["code"] == "idempotency_key_reused"

    again = sandbox.try_execute(a["id"])
    assert again.status_code == 409, "АБС не проводит исполненную операцию второй раз (контракт с узлом, ревью B)"
    assert again.json()["error"]["code"] == "already_executed"

    sandbox.bank.patch(
        "/v1/failures", json={"lose_outcome": False, "node_unavailable": True}, headers=sandbox.headers
    ).raise_for_status()
    waiting = sandbox.bank.post(
        "/v1/conveyor/applications", headers=sandbox.headers, json=online_draft("36666666666666", "998905556677")
    )
    assert waiting.status_code == 503
    assert waiting.json()["error"]["code"] == "node_unavailable"
    money_waits = sandbox.execute(b["id"])
    assert money_waits["status"] == "waiting_node"

    sandbox.bank.patch("/v1/failures", json={"node_unavailable": False}, headers=sandbox.headers).raise_for_status()
    resumed = sandbox.execute(b["id"])
    assert resumed["operation_key"] == money_waits["operation_key"], "повтор после сбоя — с тем же ключом операции"
    assert resumed["status"] == "executed"


def test_queue_lag_holds_money(sandbox: Sandbox) -> None:
    a = sandbox.apply(online_draft("37777777777777", "998906667788"))
    sandbox.bank.patch("/v1/failures", json={"queue_lag": True}, headers=sandbox.headers).raise_for_status()
    sandbox.bank.patch(
        f"/v1/conveyor/applications/{a['id']}", json={"amount": 25_000_000}, headers=sandbox.headers
    ).raise_for_status()
    time.sleep(12)
    stuck = sandbox.execute(a["id"])
    assert stuck["status"] == "refused"
    assert stuck["refusal"]["code"] == "queue_lag"


def test_audit_chain_verifies_and_anchors(sandbox: Sandbox) -> None:
    sandbox.apply(online_draft("38888888888888", "998907778899"))
    risk = sandbox.as_staff("risk-1")
    checkpoint = sandbox.node.post("/v1/audit/checkpoints", headers=risk).json()
    assert checkpoint["anchored"] is True
    report = sandbox.node.get("/v1/audit/verify", headers=risk).json()
    assert report["intact"] is True
    assert report["checkpoints_checked"] >= 1
