"""И4 на стенде: сеть кредиторов. Переключатель сети (со вторым подписантом) меняет исход сценария; новое
совпадение в другом банке останавливает зачисление до новой оценки; карта в сети — удержание на первом переводе."""

import time
from typing import Any

from tests.e2e.conftest import Sandbox

WAIT_SECONDS = 20  # уведомление оператора и пометка узла идут фоновыми тактами


def _run(sandbox: Sandbox, code: str) -> dict[str, Any]:
    response = sandbox.bank.post(f"/v1/scenarios/{code}/runs", headers=sandbox.headers)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def _client_app(run: dict[str, Any]) -> dict[str, Any]:
    app: dict[str, Any] = next(a for a in run["applications"] if a["person"] == "client" and a["application_id"])
    return app


def _codes(app: dict[str, Any]) -> set[str]:
    return {r["code"] for r in (app["last_decision"] or {}).get("reasons", [])}


def _enable_network(sandbox: Sandbox) -> None:
    risk1, risk2 = sandbox.as_staff("risk-1"), sandbox.as_staff("risk-2")
    proposal = sandbox.node.post(
        "/v1/policy/proposals", headers=risk1, json={"changes": {"network.enabled": True}, "reason": "Пилот сети"}
    )
    assert proposal.is_success, proposal.text
    approval = sandbox.node.post(f"/v1/policy/proposals/{proposal.json()['proposal_id']}/approval", headers=risk2)
    assert approval.is_success, approval.text


def test_network_switch_changes_the_outcome(sandbox: Sandbox) -> None:
    off = _client_app(_run(sandbox, "network_links_elsewhere"))
    assert off["level"] == "green", "один банк связей в других банках не видит"
    _enable_network(sandbox)
    overview = sandbox.node.get("/v1/network/overview", headers=sandbox.as_staff("risk-1")).json()
    assert overview["enabled"] and overview["available"]
    on = _client_app(_run(sandbox, "network_links_elsewhere"))
    assert on["level"] in ("yellow", "red"), on
    assert {"NETWORK_SHARED_PHONE", "NETWORK_SHARED_DEVICE"} <= _codes(on)
    series = _client_app(_run(sandbox, "network_pinfl_series"))
    assert "NETWORK_PINFL_SERIES" in _codes(series)
    assert series["action"] == "pause_for_call", "независимое основание: проверка намерения его не снимает"


def test_main_scenario_through_network(sandbox: Sandbox) -> None:
    _enable_network(sandbox)
    app = _client_app(_run(sandbox, "network_main"))
    assert app["level"] == "green"
    deadline = time.monotonic() + WAIT_SECONDS
    while True:  # уведомление оператора и пометка узла идут фоновыми тактами — посетитель нажимает АБС позже
        state = sandbox.bank.get(f"/v1/conveyor/applications/{app['application_id']}", headers=sandbox.headers)
        if state.json()["node_state"] == "reassessment_required" or time.monotonic() > deadline:
            break
        time.sleep(1)
    result = sandbox.execute(app["application_id"])
    assert (result.get("refusal") or {}).get("code") == "reassessment_required", result
    decision = sandbox.reassess(app["application_id"])["last_decision"]
    assert decision["level"] == "yellow", decision
    assert {"NETWORK_SHARED_PHONE", "NETWORK_SHARED_DEVICE"} <= {r["code"] for r in decision["reasons"]}


def test_card_in_network_holds_first_transfer(sandbox: Sandbox) -> None:
    _enable_network(sandbox)
    run = _run(sandbox, "network_card_transfer")
    app = _client_app(run)
    assert app["error"] is None, app
    transfers = sandbox.bank.get("/v1/transfers", headers=sandbox.headers).json()
    mine = [t for t in transfers if t["application_id"] == app["application_id"]]
    assert mine and mine[-1]["recommendation"]["recommended_action"] == "hold_until_confirmed", mine
