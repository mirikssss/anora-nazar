"""Сеть кредиторов в узле: переключатель со вторым подписантом, ответ сети в решении, уведомление о новом
совпадении → отказ АБС до новой оценки, сбой сети и повтор запроса перед Т2. Оператор — подделка с настоящим OPRF."""

import json
from typing import Any
from uuid import UUID

import httpx

from node.modules.applications import service as applications
from shared.network import oprf
from shared.network.client import NetworkClient
from tests.integration.conftest import KEYS, Node, online


class FakeOperator:
    def __init__(self) -> None:
        self.secret, _ = oprf.derive_key_pair(b"s" * 32, b"anora-nazar:test:1")
        self.counters: dict[str, int] = {}
        self.down = False
        self.queries: list[dict[str, Any]] = []
        self.activity: list[dict[str, Any]] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            return httpx.Response(503, json={"error": {"code": "operator_outage", "message": "Сеть недоступна"}})
        body = json.loads(request.content) if request.content else {}
        if request.url.path == "/v1/oprf/evaluations":
            evaluated = [oprf.blind_evaluate(self.secret, bytes.fromhex(b)).hex() for b in body["blinded"]]
            return httpx.Response(200, json={"kind": body["kind"], "key_version": 1, "evaluated": evaluated})
        if request.url.path == "/v1/counters/queries":
            self.queries += body["queries"]
            results = [
                {"ref": q["ref"], "as_of": "2026-10-11T09:00:00+00:00", "counters": self.counters, "confirmed": []}
                for q in body["queries"]
            ]
            return httpx.Response(200, json={"contract": "network-contract-1", "results": results})
        if request.url.path == "/v1/activity/events":
            self.activity += body["events"]
            n = len(body["events"])
            return httpx.Response(200, json={"accepted": n, "duplicates": 0, "conflicts": [], "unknown_references": []})
        return httpx.Response(404, json={"error": {"code": "not_found", "message": request.url.path}})


def connect(node: Node) -> FakeOperator:
    operator = FakeOperator()
    client = NetworkClient("http://operator", "k", timeout_seconds=5, transport=httpx.MockTransport(operator.handle))
    node.ctx.network_client = node.ctx.network_history = client
    return operator


def enable_network(node: Node, realm: UUID) -> None:
    risk1, risk2 = node.staff(realm, "risk-1"), node.staff(realm, "risk-2")
    proposal = node.client.post(
        "/v1/policy/proposals", headers=risk1, json={"changes": {"network.enabled": True}, "reason": "Пилот сети"}
    ).json()
    approved = node.client.post(f"/v1/policy/proposals/{proposal['proposal_id']}/approval", headers=risk2)
    assert approved.status_code == 200, approved.text


def notify(node: Node, realm: UUID, ref: str, notification_id: str) -> str:
    body = {"notification_id": notification_id, "ref": ref, "kinds": ["phone"], "occurred_at": "2026-10-11T09:00:00Z"}
    response = node.client.post(
        "/v1/network/notifications",
        json=body,
        headers={"Authorization": f"Bearer {KEYS['network']}", "X-Realm-Id": str(realm)},
    )
    assert response.status_code == 200, response.text
    return str(response.json()["outcome"])


def test_network_answer_and_new_match_stop_the_money_until_reassessment(node: Node) -> None:
    operator = connect(node)
    realm, off = node.new_sandbox(), node.new_sandbox()
    node.assess(off, "OFF", online("34000000000009", "998904000009", device="dev-off"))
    assert operator.queries == [], "сеть выключена по умолчанию — в сеть не уходит ничего"

    enable_network(node, realm)
    snapshot = online("34000000000001", "998904000001", device="dev-1")
    assert node.assess(realm, "A", snapshot)["level"] == "green"
    ref = operator.queries[-1]["ref"]
    assert operator.queries[-1]["watch_until"] is not None, "подписка на новые совпадения до срока оценки"
    node.tasks.deliver_outbox()
    assert [e["kind"] for e in operator.activity] == ["application"]
    assert "998904000001" not in json.dumps(operator.activity), "в сеть — только токены"

    assert notify(node, realm, ref, "N-1") == "marked"
    assert notify(node, realm, ref, "N-1") == "duplicate"
    assert node.permit(realm, "A", snapshot).json()["refusal"]["code"] == "reassessment_required"

    operator.counters = {"phone_people_30d": 2, "device_people_30d": 2}
    again = node.assess(realm, "A", snapshot)
    assert again["level"] == "yellow"
    assert {"NETWORK_SHARED_PHONE", "NETWORK_SHARED_DEVICE"} <= {r["code"] for r in again["reasons"]}
    record = node.client.get(f"/v1/decisions/{again['decision_id']}", headers=node.staff(realm, "risk-1")).json()
    assert record["record"]["inputs"]["network"]["counters"]["phone_people_30d"] == 2, "ответ сети — в записи"


def test_network_down_is_not_green_by_default_and_is_retried_before_disbursement(node: Node) -> None:
    operator = connect(node)
    realm = node.new_sandbox()
    enable_network(node, realm)
    operator.down = True
    still_down = online("35000000000001", "998905000001")
    first = node.assess(realm, "DOWN", still_down)
    assert "SYSTEM_NETWORK_UNAVAILABLE" in {r["code"] for r in first["reasons"]}
    assert node.permit(realm, "DOWN", still_down).json()["permit"] is not None, "узел работает без сети"

    back = online("35000000000002", "998905000002")
    node.assess(realm, "BACK", back)
    operator.down = False
    assert node.permit(realm, "BACK", back).json()["refusal"]["code"] == "reassessment_required"
    with node.ctx.db.transaction() as session:
        app_id = applications.find_id(session, realm, "BACK")
        assert app_id is not None
        assert applications.get_by_id(session, app_id).reassessment_cause["network_available"] is True
