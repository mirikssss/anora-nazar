"""Чистая логика ядра: порядок версий, проверки разрешения, отставание очереди, хеши и дерево Меркла."""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from node.modules.applications.domain import VersionOutcome, classify_version
from node.modules.audit.domain import GENESIS, StoredRecord, entry, first_break, record_hash
from node.modules.ingest.domain import lag_seconds
from node.modules.permits.domain import ApplicationFacts, OperationFacts, PermitRequest, Refusal, check, next_status
from shared.crypto.canonical_json import canonical_bytes
from shared.crypto.merkle import merkle_root

NOW = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)


def test_version_order() -> None:
    assert classify_version(None, 1) is VersionOutcome.APPLIED
    assert classify_version(None, 2) is VersionOutcome.GAP
    assert classify_version(3, 4) is VersionOutcome.APPLIED
    assert classify_version(3, 3) is VersionOutcome.SAME
    assert classify_version(3, 2) is VersionOutcome.STALE
    assert classify_version(3, 5) is VersionOutcome.GAP


def _facts(**overrides: object) -> ApplicationFacts:
    base: dict[str, object] = {
        "status": "active",
        "current_version": 1,
        "assessed_version": 1,
        "needs_reassessment": False,
        "reassessment_cause": None,
        "version_gap": False,
        "assessment_point": "T1",
        "assessment_outcome": "assessed",
        "assessment_valid_until": NOW + timedelta(hours=1),
    }
    return ApplicationFacts(**{**base, **overrides})  # type: ignore[arg-type]


OP = OperationFacts(allowed_amount=100, expected_account="ACC", existing_statuses=(), active_hold_bases=())
REQ = PermitRequest(application_version=1, operation_type="disbursement", tranche=1, amount=100, account="ACC")


def test_permit_checks_and_their_order() -> None:
    assert check(_facts(), OP, REQ, NOW, 0.0, 10) is None
    cases = [
        (_facts(status="cancelled", needs_reassessment=True), Refusal.APPLICATION_CANCELLED),
        (_facts(version_gap=True, needs_reassessment=True), Refusal.VERSION_GAP),
        (_facts(current_version=2, needs_reassessment=True), Refusal.VERSION_MISMATCH),
        (_facts(assessed_version=None), Refusal.ASSESSMENT_REQUIRED),
        (_facts(needs_reassessment=True), Refusal.REASSESSMENT_REQUIRED),
        (_facts(assessment_outcome="stopped_by_norm"), Refusal.STOPPED_BY_NORM),
        (_facts(assessment_point="T4"), Refusal.WRONG_STAGE),
        (_facts(assessment_valid_until=NOW), Refusal.ASSESSMENT_EXPIRED),
    ]
    for facts, code in cases:
        result = check(facts, OP, REQ, NOW, 0.0, 10)
        assert result is not None and result.code is code, code
    lagging = check(_facts(), OP, REQ, NOW, None, 10)
    assert lagging is not None and lagging.code is Refusal.QUEUE_LAG
    held = OperationFacts(100, "ACC", (), ({"hold_id": "h"},))
    assert check(_facts(), held, REQ, NOW, 0.0, 10).code is Refusal.ACTIVE_HOLD  # type: ignore[union-attr]
    more = PermitRequest(1, "disbursement", 1, 101, "ACC")
    assert check(_facts(), OP, more, NOW, 0.0, 10).code is Refusal.CONDITIONS_MISMATCH  # type: ignore[union-attr]
    done = OperationFacts(100, "ACC", ("executed",), ())
    assert check(_facts(), done, REQ, NOW, 0.0, 10).code is Refusal.ALREADY_EXECUTED  # type: ignore[union-attr]


def test_outcome_transitions() -> None:
    assert next_status("reserved", "executed") == "executed"
    assert next_status("unknown", "not_executed") == "not_executed"
    assert next_status("executed", "executed") == "executed"
    assert next_status("executed", "not_executed") is None


def test_lag_is_the_older_of_backlog_and_staleness() -> None:
    assert lag_seconds(0, None, NOW, NOW) == 0
    assert lag_seconds(2, NOW - timedelta(seconds=15), NOW, NOW) == 15
    assert lag_seconds(0, None, NOW - timedelta(seconds=12), NOW) == 12


def test_canonical_json_ignores_key_order() -> None:
    assert canonical_bytes({"b": 1, "a": [1, 2]}) == canonical_bytes({"a": [1, 2], "b": 1})


def test_merkle_root_matches_rfc9162_definition() -> None:
    leaf = lambda d: hashlib.sha256(b"\x00" + d).digest()  # noqa: E731
    node = lambda left, right: hashlib.sha256(b"\x01" + left + right).digest()  # noqa: E731
    a, b, c = b"a", b"b", b"c"
    assert merkle_root([a]) == leaf(a)
    assert merkle_root([a, b, c]) == node(node(leaf(a), leaf(b)), leaf(c))


def test_first_break_finds_the_edited_record() -> None:
    realm = uuid4()
    records, prev = [], GENESIS
    for seq in range(1, 4):
        payload = {"n": seq}
        digest = record_hash(prev, entry(realm, seq, "k", payload, NOW))
        records.append(StoredRecord(seq, "k", payload, NOW, prev, digest))
        prev = digest
    assert first_break(realm, records) is None
    records[1] = StoredRecord(2, "k", {"n": 99}, NOW, records[1].prev_hash, records[1].hash)
    broken = first_break(realm, records)
    assert broken is not None and (broken.seq, broken.problem) == (2, "content_changed")
