"""И3: проверка намерения, дела и исходы, стоп-лист и Т6, второй подписант порогов, Т3, Т5, эскалация."""

from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from node.modules.applications import service as applications
from node.modules.permits import service as permits
from tests.integration.conftest import Node, online


def _client_event(node: Node, realm: UUID, type_: str, app: str, pinfl: str, **extra: Any) -> None:
    node.event(realm, app, None, type_=type_, payload={"subject_pinfl": pinfl, "application_id": app, **extra})


def _hold(node: Node, realm: UUID, app: str, check: str) -> None:
    with node.ctx.db.transaction() as session:
        app_id = applications.find_id(session, realm, app)
        assert app_id is not None
        row = applications.get_by_id(session, app_id)
        permits.place_hold(
            session,
            realm_id=realm,
            application_id=app_id,
            external_id=app,
            decision_id=row.latest_decision_id or uuid4(),
            required_check=check,
            basis=[],
            config=node.ctx.config,
            now=node.clock.now(),
        )


def _holds(node: Node, realm: UUID, app: str) -> list[str]:
    with node.ctx.db.transaction() as session:
        app_id = applications.find_id(session, realm, app)
        assert app_id is not None
        return [h.required_check for h in permits.active_holds(session, app_id)]


def _queue(node: Node, realm: UUID, user: str, queue: str) -> list[dict[str, Any]]:
    response = node.client.get(f"/v1/cases?queue={queue}", headers=node.staff(realm, user))
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()
    return items


def test_calm_intent_answers_release_the_intent_check(node: Node) -> None:
    realm, pinfl = node.new_sandbox(), "31000000000001"
    snapshot = online(pinfl, "998901000001", employee=None)
    node.assess(realm, "A", snapshot)
    _hold(node, realm, "A", "intent_check")
    answers = [
        {"question": "purpose_own_need", "answer": "yes_own"},
        {"question": "someone_instructs", "answer": "no_one"},
    ]
    _client_event(node, realm, "client.intent_answers", "A", pinfl, answers=answers)
    assert _holds(node, realm, "A") == []
    assert node.permit(realm, "A", snapshot).json()["granted"] is True


def test_pressure_button_pauses_opens_case_and_reassessment_is_red(node: Node) -> None:
    realm, pinfl = node.new_sandbox(), "31000000000002"
    snapshot = online(pinfl, "998901000002", employee=None)
    node.assess(realm, "A", snapshot)
    _client_event(node, realm, "client.pressure_reported", "A", pinfl)
    assert _holds(node, realm, "A") == ["pause_for_call"]
    assert node.permit(realm, "A", snapshot).json()["refusal"]["code"] == "reassessment_required"
    queue = _queue(node, realm, "analyst-1", "online")
    assert [a["application_id"] for c in queue for a in c["applications"]] == ["A"]
    again = node.assess(realm, "A", snapshot)
    assert again["level"] == "red"
    assert any(r["code"] == "PRODUCT_CLIENT_REPORTED_PRESSURE" for r in again["reasons"])


def test_alarming_answer_escalates_to_call(node: Node) -> None:
    realm, pinfl = node.new_sandbox(), "31000000000003"
    node.assess(realm, "A", online(pinfl, "998901000003", employee=None))
    _hold(node, realm, "A", "intent_check")
    answers = [
        {"question": "purpose_own_need", "answer": "no_other_person"},
        {"question": "someone_instructs", "answer": "no_one"},
    ]
    _client_event(node, realm, "client.intent_answers", "A", pinfl, answers=answers)
    assert set(_holds(node, realm, "A")) == {"intent_check", "pause_for_call"}


def test_group_case_decisions_outcome_stop_list_and_t6(node: Node) -> None:
    realm = node.new_sandbox()
    ring = {"device": "dev-ring-7", "address": "махалля Навбахор, дом 9"}
    snapshots = {
        f"R{i}": online(f"3200000000010{i}", "998902220099", branch="BR-02", employee=None, **ring) for i in range(1, 4)
    }
    for app, snapshot in snapshots.items():
        node.assess(realm, app, snapshot)
    node.assess(realm, "R1", snapshots["R1"])  # R1 помечена «нужна новая оценка» — конвейер переоценивает
    group = _queue(node, realm, "control-1", "group")
    assert len(group) == 1 and {a["application_id"] for a in group[0]["applications"]} == {"R1", "R2", "R3"}
    case_id = group[0]["case_id"]
    control, own_branch = node.staff(realm, "control-1"), node.staff(realm, "control-2")
    assert (
        node.client.post(f"/v1/cases/{case_id}/assignment", headers=own_branch).json()["error"]["code"]
        == "own_division"
    )
    assert node.client.post(f"/v1/cases/{case_id}/assignment", headers=control).status_code == 200
    graph = node.client.get(f"/v1/cases/{case_id}/graph", headers=control).json()
    assert any(e["rare"] and e["type"] == "shared_identifier" for e in graph["edges"])
    released = node.client.post(
        f"/v1/cases/{case_id}/applications/R3/decision",
        headers=control,
        json={"action": "release", "role": "uninvolved", "basis": "Сосед по адресу, проверено звонком"},
    )
    assert released.status_code == 200 and _holds(node, realm, "R3") == []

    node.clock.set(node.clock.now() + timedelta(minutes=5))
    node.watermark(realm)
    later = online("32000000000199", "998902220199", employee=None, device="dev-ring-7")
    node.assess(realm, "LATER", later)
    closed = node.client.post(
        f"/v1/cases/{case_id}/outcome",
        headers=control,
        json={"outcome": "confirmed_fraud", "checklist": {"call_applicants": True}, "note": "Подставные заёмщики"},
    )
    assert closed.status_code == 200, closed.text
    assert node.permit(realm, "R1", snapshots["R1"]).json()["refusal"]["code"] == "application_refused"
    node.assess(realm, "R3", snapshots["R3"])  # помечена новой заявкой LATER — конвейер переоценивает
    assert node.permit(realm, "R3", snapshots["R3"]).json()["granted"] is True, "проверенная связь не держит снова"
    labels = node.sql("select kind, typology, source from labels order by id")
    assert {tuple(row) for row in labels} == {("positive", "F2", "internal_control")}
    assert len(labels) == 2, "метку получают участники схемы, не посторонний"
    assert node.permit(realm, "LATER", later).json()["refusal"]["code"] == "reassessment_required", "Т6"
    fresh = node.assess(realm, "NEW", online("32000000000299", "998902220099", employee=None))
    assert fresh["level"] == "red"
    assert any(r["code"] == "PRODUCT_CONFIRMED_CASE_IDENTIFIER" for r in fresh["reasons"])
    timeline = node.client.get(f"/v1/cases/{case_id}", headers=control).json()["timeline"]
    assert [e["kind"] for e in timeline][-1] == "closed" and all(e["audit_seq"] > 0 for e in timeline)


def test_threshold_change_needs_second_signer_and_stays_in_sandbox(node: Node) -> None:
    realm, other = node.new_sandbox(), node.new_sandbox()
    risk1, risk2 = node.staff(realm, "risk-1"), node.staff(realm, "risk-2")
    proposal = node.client.post(
        "/v1/policy/proposals",
        headers=risk1,
        json={"changes": {"group.min_independent_rare_links": 3}, "reason": "Меньше ложных групп"},
    ).json()
    own = node.client.post(f"/v1/policy/proposals/{proposal['proposal_id']}/approval", headers=risk1)
    assert own.status_code == 403 and own.json()["error"]["code"] == "second_signer_required"
    approved = node.client.post(f"/v1/policy/proposals/{proposal['proposal_id']}/approval", headers=risk2).json()
    version = approved["resulting_version"]
    assert node.client.get("/v1/policy", headers=risk1).json()["active_version"] == version
    assert node.client.get("/v1/policy", headers=node.staff(other, "risk-1")).json()["active_version"] == "policy-v3"
    bad = node.client.post(
        "/v1/policy/proposals", headers=risk1, json={"changes": {"index.window_days": 30}, "reason": "Нельзя"}
    )
    assert bad.status_code == 422
    decision = node.assess(realm, "A", online("33000000000001", "998903000001", employee=None))
    record = node.client.get(f"/v1/decisions/{decision['decision_id']}", headers=risk1).json()["record"]
    assert record["versions"]["policy"] == version


def _transfer(node: Node, realm: UUID, app: str, card: str) -> dict[str, Any]:
    now = node.clock.now()
    response = node.post(
        "core_banking",
        "/v1/transfers/recommendations",
        realm,
        json={
            "application_id": app,
            "transfer_id": str(uuid4()),
            "amount": 29_000_000,
            "recipient_card": card,
            "recipient_is_new": True,
            "balance_before_credit": 100_000,
            "credited_at": (now - timedelta(hours=1)).isoformat(),
            "requested_at": now.isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_first_transfer_recommendation(node: Node) -> None:
    realm, card = node.new_sandbox(), "8600123412341234"
    node.assess(realm, "A", online("34000000000001", "998904000001", employee=None))
    node.assess(realm, "B", online("34000000000002", "998904000002", employee=None))
    first = _transfer(node, realm, "A", card)
    assert first["level"] == "yellow" and first["recommended_action"] == "allow"
    second = _transfer(node, realm, "B", card)
    assert second["level"] == "red" and second["recommended_action"] == "hold_until_confirmed"
    assert any(a["point"] == "T3" for c in _queue(node, realm, "analyst-1", "online") for a in c["applications"])
    replay = node.client.get(
        f"/v1/decisions/{second['recommendation_id']}/replay", headers=node.staff(realm, "analyst-1")
    ).json()
    assert replay["identical"] is True


def _program(pinfl: str, phone: str, supplier: str) -> dict[str, Any]:
    snapshot = online(pinfl, phone)
    snapshot.update(
        {
            "channel": "program",
            "disbursement_account": None,
            "program": {
                "helper_id": "HLP-1",
                "supplier_inn": supplier,
                "supplier_account": "20208000900100001001",
                "item_code": "cow",
                "unit": "head",
                "unit_price": 12_000_000,
                "quantity": 2,
                "district": "Район 1",
            },
        }
    )
    return snapshot


def test_batch_acceptance_acts_hold_supplier_payment(node: Node) -> None:
    realm = node.new_sandbox()
    snapshot = _program("35000000000001", "998905000001", "305000001")
    node.assess(realm, "P", snapshot, point="T4")
    for n in range(5):
        node.event(
            realm,
            f"ACT-{n}",
            None,
            type_="program.acceptance_act",
            entity_type="acceptance_act",
            payload={
                "act_id": f"ACT-{n}",
                "application_id": "P",
                "signer_id": "HLP-1",
                "signer_role": "helper",
                "signed_on": node.clock.now().date().isoformat(),
                "invoice_amount": 24_000_000,
            },
        )
    response = node.post(
        "core_banking",
        "/v1/permits",
        realm,
        idem=str(uuid4()),
        json={
            "application_id": "P",
            "application_version": 1,
            "operation_type": "supplier_payment",
            "tranche": 1,
            "amount": 24_000_000,
            "account": "20208000900100001001",
            "acceptance_act_id": "ACT-4",
        },
    )
    assert response.json()["refusal"]["code"] == "active_hold"
    group = _queue(node, realm, "control-1", "group")
    assert group and group[0]["zone"] == 3


def test_overdue_case_escalates(node: Node) -> None:
    realm, pinfl = node.new_sandbox(), "36000000000001"
    node.assess(realm, "A", online(pinfl, "998906000001", employee=None))
    _client_event(node, realm, "client.pressure_reported", "A", pinfl)
    node.clock.set(node.clock.now() + timedelta(hours=node.ctx.cases_config.deadlines.call_hours + 1))
    node.tasks.escalate_cases()
    assert _queue(node, realm, "analyst-1", "online")[0]["status"] == "escalated"
