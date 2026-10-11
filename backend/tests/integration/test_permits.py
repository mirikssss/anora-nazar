"""Разрешения: резерв одной транзакцией, гонка с пометкой, идемпотентность, просрочка и сверка."""

import threading
import time
from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.integration.conftest import Node, online

PHONE = "998901110000"
DEVICE = "dev-shared"


def _granted(response: object) -> bool:
    return bool(response.json()["granted"])  # type: ignore[attr-defined]


def test_green_application_gets_signed_single_use_permit(node: Node) -> None:
    realm = node.new_sandbox()
    snap = online("30000000000001", PHONE)
    node.assess(realm, "A", snap)
    first = node.permit(realm, "A", snap, key="op-1")
    assert _granted(first)
    payload = first.json()["permit"]["payload"]
    assert payload["operation_key"] == "op-1"
    assert node.ctx.signer.verify_key is not None

    second = node.permit(realm, "A", snap, key="op-2")
    assert second.json()["refusal"]["code"] == "operation_in_progress"


def test_same_key_same_params_returns_same_answer_and_other_params_conflict(node: Node) -> None:
    realm = node.new_sandbox()
    snap = online("30000000000002", PHONE)
    node.assess(realm, "A", snap)
    first = node.permit(realm, "A", snap, key="op-1").json()
    repeat = node.permit(realm, "A", snap, key="op-1").json()
    assert repeat == first
    conflict = node.permit(realm, "A", snap, key="op-1", amount=snap["loan"]["amount"] - 1)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_key_reused"


def test_executed_operation_cannot_run_again_with_a_new_key(node: Node) -> None:
    realm = node.new_sandbox()
    snap = online("30000000000003", PHONE)
    node.assess(realm, "A", snap)
    assert _granted(node.permit(realm, "A", snap, key="op-1"))
    assert node.outcome(realm, "op-1", "executed").json()["status"] == "executed"
    assert node.outcome(realm, "op-1", "executed").status_code == 200
    assert node.outcome(realm, "op-1", "not_executed").status_code == 409
    assert node.permit(realm, "A", snap, key="op-2").json()["refusal"]["code"] == "already_executed"


def test_failed_attempt_frees_the_operation_for_a_new_attempt(node: Node) -> None:
    realm = node.new_sandbox()
    snap = online("30000000000004", PHONE)
    node.assess(realm, "A", snap)
    assert _granted(node.permit(realm, "A", snap, key="op-1"))
    node.outcome(realm, "op-1", "not_executed")
    assert _granted(node.permit(realm, "A", snap, key="op-2"))


def test_database_forbids_two_live_permits_for_one_operation(node: Node) -> None:
    realm = node.new_sandbox()
    snap = online("30000000000005", PHONE)
    node.assess(realm, "A", snap)
    assert _granted(node.permit(realm, "A", snap, key="op-1"))
    with pytest.raises(IntegrityError):
        node.sql("""INSERT INTO permits SELECT gen_random_uuid(), realm_id, application_id, operation_type, tranche,
                    'op-dup', application_version, decision_id, amount, account, 'reserved', payload, signature,
                    key_id, reserved_at, expires_at, finished_at FROM permits WHERE operation_key = 'op-1'""")


def test_conditions_must_match_the_assessed_version(node: Node) -> None:
    realm = node.new_sandbox()
    snap = online("30000000000006", PHONE)
    node.assess(realm, "A", snap)
    refused = node.permit(realm, "A", snap, amount=snap["loan"]["amount"] + 1).json()
    assert refused["refusal"]["code"] == "conditions_mismatch"
    assert node.permit(realm, "A", snap, version=2).json()["refusal"]["code"] == "version_mismatch"


def test_expired_assessment_is_not_used(node: Node) -> None:
    realm = node.new_sandbox()
    snap = online("30000000000007", PHONE)
    node.assess(realm, "A", snap)
    node.clock.set(node.clock.now() + timedelta(hours=24, seconds=1))
    node.watermark(realm)
    assert node.permit(realm, "A", snap).json()["refusal"]["code"] == "assessment_expired"


def test_lost_outcome_becomes_unknown_then_reconciled_with_core_banking(node: Node) -> None:
    realm = node.new_sandbox()
    snap = online("30000000000008", PHONE)
    node.assess(realm, "A", snap)
    assert _granted(node.permit(realm, "A", snap, key="op-lost"))

    node.clock.set(node.clock.now() + timedelta(seconds=121))
    node.tasks.expire_reserved()
    node.watermark(realm)
    assert node.permit(realm, "A", snap, key="op-new").json()["refusal"]["code"] == "operation_in_progress"

    node.bank.operations["op-lost"] = "in_progress"
    node.tasks.reconcile_unknown()
    assert node.sql("SELECT status FROM permits WHERE operation_key = 'op-lost'")[0][0] == "unknown"

    node.bank.operations["op-lost"] = "executed"
    node.tasks.reconcile_unknown()
    assert node.sql("SELECT status FROM permits WHERE operation_key = 'op-lost'")[0][0] == "executed"
    assert node.permit(realm, "A", snap, key="op-new-2").json()["refusal"]["code"] == "already_executed"


def test_unknown_operation_missing_in_core_banking_is_settled_as_not_executed(node: Node) -> None:
    realm = node.new_sandbox()
    snap = online("30000000000009", PHONE)
    node.assess(realm, "A", snap)
    node.permit(realm, "A", snap, key="op-ghost")
    node.clock.set(node.clock.now() + timedelta(seconds=121))
    node.tasks.expire_reserved()
    node.tasks.reconcile_unknown()
    node.watermark(realm)
    assert node.sql("SELECT status FROM permits WHERE operation_key = 'op-ghost'")[0][0] == "not_executed"
    assert _granted(node.permit(realm, "A", snap))


def test_queue_lag_or_missing_watermark_makes_money_wait(node: Node) -> None:
    realm = node.new_sandbox()
    snap = online("30000000000010", PHONE)
    node.assess(realm, "A", snap)
    node.watermark(realm, pending=3, oldest=node.clock.now() - timedelta(seconds=11))
    assert node.permit(realm, "A", snap).json()["refusal"]["code"] == "queue_lag"
    node.sql("DELETE FROM watermarks")
    assert node.permit(realm, "A", snap).json()["refusal"]["code"] == "queue_lag"


def test_mark_before_reserve_refuses_and_reserve_before_mark_is_counted(node: Node) -> None:
    realm = node.new_sandbox()
    a = online("30000000000011", PHONE, device=DEVICE)
    node.assess(realm, "A", a)
    assert _granted(node.permit(realm, "A", a, key="op-a"))

    b = online("30000000000012", PHONE, device=DEVICE)
    marked = node.assess(realm, "B", b)["marked_applications"]
    assert marked == ["A"]
    metrics = node.client.get("/v1/system/metrics", headers=node.staff(realm, "risk-1")).json()
    assert metrics["marks"]["marked_after_reserve"] == 1

    c = online("30000000000013", "998901119999", device="dev-c", address="ул. Навои 1")
    node.assess(realm, "C", c)
    d = online("30000000000014", "998901119999", device="dev-c", address="ул. Навои 1")
    node.assess(realm, "D", d)
    assert node.permit(realm, "C", c).json()["refusal"]["code"] == "reassessment_required"


def test_reserve_and_marking_are_serialized_on_the_application_row(node: Node) -> None:
    """Пока транзакция резерва держит строку заявки, пометка ждёт; после фиксации пометка проходит."""
    realm = node.new_sandbox()
    a = online("30000000000015", PHONE, device=DEVICE)
    node.assess(realm, "A", a)
    app_id = node.sql("SELECT id FROM applications WHERE external_id = 'A'")[0][0]

    finished = threading.Event()

    def mark_via_linked_application() -> None:
        node.assess(realm, "B", online("30000000000016", PHONE, device=DEVICE))
        finished.set()

    with node.ctx.db.engine.connect() as holder:
        tx = holder.begin()
        holder.execute(text("SELECT id FROM applications WHERE id = :id FOR UPDATE"), {"id": app_id})
        worker = threading.Thread(target=mark_via_linked_application)
        worker.start()
        time.sleep(0.5)
        assert not finished.is_set(), "пометка не должна пройти, пока строка заблокирована резервом"
        tx.commit()
    worker.join(timeout=10)
    assert finished.is_set()
    assert node.sql("SELECT needs_reassessment FROM applications WHERE id = :id", id=app_id)[0][0] is True
