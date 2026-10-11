"""Чистая логика журнала: хеш записи, корень Меркла, поиск первой изменённой записи."""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from shared.crypto.canonical_json import canonical_bytes
from shared.crypto.merkle import merkle_root

GENESIS = "0" * 64


def entry(realm_id: UUID, seq: int, kind: str, payload: dict[str, Any], recorded_at: datetime) -> dict[str, Any]:
    return {
        "realm_id": str(realm_id),
        "seq": seq,
        "kind": kind,
        "payload": payload,
        "recorded_at": recorded_at.isoformat(),
    }


def record_hash(prev_hash: str, content: dict[str, Any]) -> str:
    """H(хеш предыдущей ‖ канонический JSON записи по RFC 8785)."""
    return hashlib.sha256(bytes.fromhex(prev_hash) + canonical_bytes(content)).hexdigest()


def root_of(hashes: Sequence[str]) -> str:
    return merkle_root([bytes.fromhex(h) for h in hashes]).hex()


def checkpoint_payload(realm_id: UUID, seq: int, root: str, head: str, created_at: datetime) -> dict[str, Any]:
    return {
        "realm_id": str(realm_id),
        "seq": seq,
        "merkle_root": root,
        "head_hash": head,
        "created_at": created_at.isoformat(),
    }


@dataclass(frozen=True)
class StoredRecord:
    seq: int
    kind: str
    payload: dict[str, Any]
    recorded_at: datetime
    prev_hash: str
    hash: str


@dataclass(frozen=True)
class ChainBreak:
    seq: int
    kind: str
    problem: str


def first_break(realm_id: UUID, records: Sequence[StoredRecord]) -> ChainBreak | None:
    """Идёт по цепочке с начала и возвращает первую запись, которая не сходится."""
    prev = GENESIS
    for expected_seq, record in enumerate(records, start=1):
        if record.seq != expected_seq:
            return ChainBreak(expected_seq, record.kind, "missing_record")
        if record.prev_hash != prev:
            return ChainBreak(record.seq, record.kind, "broken_link")
        content = entry(realm_id, record.seq, record.kind, record.payload, record.recorded_at)
        if record_hash(prev, content) != record.hash:
            return ChainBreak(record.seq, record.kind, "content_changed")
        prev = record.hash
    return None
