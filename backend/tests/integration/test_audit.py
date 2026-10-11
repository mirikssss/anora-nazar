"""Журнал: правка записи находится на ней самой, переписанный журнал — по якорю."""

import json

from node.modules.audit.domain import GENESIS, entry, record_hash
from tests.integration.conftest import Node, online


def _checkpoint(node: Node, realm: object) -> dict[str, object]:
    staff = node.staff(realm, "risk-1")  # type: ignore[arg-type]
    return node.client.post("/v1/audit/checkpoints", headers=staff).json()


def _verify(node: Node, realm: object) -> dict[str, object]:
    return node.client.get("/v1/audit/verify", headers=node.staff(realm, "risk-1")).json()  # type: ignore[arg-type]


def test_chain_verifies_and_checkpoint_is_anchored(node: Node) -> None:
    realm = node.new_sandbox()
    node.assess(realm, "A", online("33000000000001", "998904440001"))
    assert _checkpoint(node, realm)["anchored"] is True
    report = _verify(node, realm)
    assert report["intact"] is True
    assert report["records_checked"] >= 1


def test_edited_record_is_found_as_the_first_break(node: Node) -> None:
    realm = node.new_sandbox()
    for i in range(3):
        node.assess(realm, f"A{i}", online(f"3300000000001{i}", f"99890444001{i}"))
    node.sql(
        "UPDATE audit_records SET payload = jsonb_set(payload, '{level}', '\"red\"') "
        "WHERE realm_id = :realm AND seq = 2",
        realm=str(realm),
    )
    report = _verify(node, realm)
    assert report["intact"] is False
    assert report["first_break"] == {"seq": 2, "kind": "decision.made", "problem": "content_changed"}


def test_rewritten_journal_is_caught_by_the_anchor(node: Node) -> None:
    realm = node.new_sandbox()
    for i in range(3):
        node.assess(realm, f"A{i}", online(f"3300000000002{i}", f"99890444002{i}"))
    _checkpoint(node, realm)

    rows = node.sql(
        "SELECT seq, kind, payload, recorded_at FROM audit_records WHERE realm_id = :r ORDER BY seq", r=str(realm)
    )
    prev = GENESIS
    for seq, kind, original, recorded_at in rows:
        payload = {**original, "level": "red"} if seq == 1 else original
        digest = record_hash(prev, entry(realm, seq, kind, payload, recorded_at))
        node.sql(
            "UPDATE audit_records SET payload = CAST(:p AS jsonb), prev_hash = :prev, hash = :h "
            "WHERE realm_id = :r AND seq = :s",
            p=json.dumps(payload),
            prev=prev,
            h=digest,
            r=str(realm),
            s=seq,
        )
        prev = digest
    report = _verify(node, realm)
    assert report["first_break"] is None, "переписанная цепочка сходится сама с собой"
    assert report["anchor_mismatch"]["problem"] == "root_differs"
    assert report["intact"] is False
