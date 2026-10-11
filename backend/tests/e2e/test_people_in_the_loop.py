"""И3 на стенде: заёмщик проходит проверку намерения до зачисления; кнопка «Меня просят» ставит паузу и дело;
сценарий второй зоны открывает дело группы у внутреннего контроля."""

import time
from typing import Any

from tests.e2e.conftest import Sandbox

WAIT_SECONDS = 20  # доставка уведомлений узла в банк идёт фоновым тактом


def _run(sandbox: Sandbox, code: str) -> list[dict[str, Any]]:
    response = sandbox.bank.post(f"/v1/scenarios/{code}/runs", headers=sandbox.headers)
    assert response.status_code == 201, response.text
    applications: list[dict[str, Any]] = response.json()["applications"]
    return applications


def _screen(sandbox: Sandbox, app_id: str) -> dict[str, Any]:
    body: dict[str, Any] = (
        sandbox.bank.get(f"/v1/borrower/applications/{app_id}", headers=sandbox.headers).raise_for_status().json()
    )
    return body


def _wait_screen(sandbox: Sandbox, app_id: str, expected: str) -> dict[str, Any]:
    deadline = time.monotonic() + WAIT_SECONDS
    while True:
        screen = _screen(sandbox, app_id)
        if screen["screen"] == expected or time.monotonic() > deadline:
            return screen
        time.sleep(1)


def test_calm_intent_answers_lead_to_disbursement(sandbox: Sandbox) -> None:
    app = _run(sandbox, "zone1_intent_check")[0]
    screen = _screen(sandbox, app["application_id"])
    assert screen["screen"] == "intent_check", screen
    calm = [{"question": q["code"], "answer": q["answers"][0]["code"]} for q in screen["questions"]["questions"]]
    sandbox.bank.post(
        f"/v1/borrower/applications/{app['application_id']}/intent-answers",
        headers=sandbox.headers,
        json={"answers": calm},
    ).raise_for_status()
    assert _wait_screen(sandbox, app["application_id"], "approved")["screen"] == "approved"
    assert sandbox.execute(app["application_id"])["status"] == "executed"


def test_pressure_button_pauses_and_opens_case(sandbox: Sandbox) -> None:
    app = _run(sandbox, "honest_online")[0]
    sandbox.bank.post(
        f"/v1/borrower/applications/{app['application_id']}/pressure", headers=sandbox.headers
    ).raise_for_status()
    assert _screen(sandbox, app["application_id"])["screen"] == "pause"
    assert sandbox.execute(app["application_id"])["status"] == "refused"
    queue = sandbox.node.get("/v1/cases?queue=online", headers=sandbox.as_staff("analyst-1")).json()
    assert any(a["application_id"] == app["application_id"] for c in queue for a in c["applications"])


def test_second_branch_scenario_opens_group_case(sandbox: Sandbox) -> None:
    first, second = _run(sandbox, "zone2_second_branch")
    assert second["action"] == "internal_review"
    control = sandbox.as_staff("control-1")
    queue = sandbox.node.get("/v1/cases?queue=group", headers=control).json()
    case = next(c for c in queue if any(a["application_id"] == second["application_id"] for a in c["applications"]))
    graph = sandbox.node.get(f"/v1/cases/{case['case_id']}/graph", headers=control).json()
    assert any(e["rare"] for e in graph["edges"])
    detail = sandbox.node.get(f"/v1/cases/{case['case_id']}", headers=control).json()
    assert detail["applications"][0]["applicant"]["full"] is False
    assert sandbox.execute(first["application_id"])["refusal"]["code"] == "reassessment_required"
