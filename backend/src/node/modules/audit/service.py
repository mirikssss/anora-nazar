"""Журнал: запись в той же транзакции, контрольные точки с подписью и якорем, проверка целостности."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from node.modules.audit import repository
from node.modules.audit.domain import (
    GENESIS,
    ChainBreak,
    StoredRecord,
    checkpoint_payload,
    entry,
    first_break,
    record_hash,
    root_of,
)
from node.modules.audit.models import AuditCheckpoint
from shared.crypto.signing import Signer


def append(session: Session, realm_id: UUID, kind: str, payload: dict[str, Any], now: datetime) -> int:
    repository.lock_chain(session, realm_id)
    current = repository.head(session, realm_id)
    seq, prev = (1, GENESIS) if current is None else (current[0] + 1, current[1])
    digest = record_hash(prev, entry(realm_id, seq, kind, payload, now))
    repository.insert_record(
        session,
        {
            "realm_id": realm_id,
            "seq": seq,
            "kind": kind,
            "payload": payload,
            "recorded_at": now,
            "prev_hash": prev,
            "hash": digest,
        },
    )
    return seq


def create_checkpoint(session: Session, realm_id: UUID, signer: Signer, now: datetime) -> AuditCheckpoint | None:
    """Подписанная контрольная точка по всем записям контура; ничего нового — None."""
    repository.lock_chain(session, realm_id)
    stored = repository.records(session, realm_id)
    if not stored:
        return None
    last = repository.last_checkpoint(session, realm_id)
    if last is not None and last.seq == stored[-1].seq:
        return None
    root = root_of([r.hash for r in stored])
    payload = checkpoint_payload(realm_id, stored[-1].seq, root, stored[-1].hash, now)
    checkpoint = AuditCheckpoint(
        realm_id=realm_id,
        seq=stored[-1].seq,
        merkle_root=root,
        head_hash=stored[-1].hash,
        signature=signer.sign(payload),
        key_id=signer.key_id,
        created_at=now,
        anchored_at=None,
        anchor_error=None,
    )
    repository.add_checkpoint(session, checkpoint)
    return checkpoint


@dataclass(frozen=True)
class AnchorMismatch:
    seq: int
    problem: str


@dataclass(frozen=True)
class VerificationReport:
    records_checked: int
    first_break: ChainBreak | None
    checkpoints_checked: int
    anchor_mismatch: AnchorMismatch | None

    @property
    def intact(self) -> bool:
        return self.first_break is None and self.anchor_mismatch is None


def verify(session: Session, realm_id: UUID, anchored_roots: dict[int, str]) -> VerificationReport:
    """Цепочка проверяется заново с первой записи, затем корни сверяются с якорями, которые хранит не узел.

    Переписанный целиком журнал сходится сам с собой, но не совпадает с якорем.
    """
    stored = [
        StoredRecord(r.seq, r.kind, r.payload, r.recorded_at, r.prev_hash, r.hash)
        for r in repository.records(session, realm_id)
    ]
    broken = first_break(realm_id, stored)
    mismatch: AnchorMismatch | None = None
    hashes = [r.hash for r in stored]
    for seq in sorted(anchored_roots):
        if seq > len(hashes):
            mismatch = AnchorMismatch(seq, "records_missing")
            break
        if root_of(hashes[:seq]) != anchored_roots[seq]:
            mismatch = AnchorMismatch(seq, "root_differs")
            break
    return VerificationReport(len(stored), broken, len(anchored_roots), mismatch)


def page(session: Session, realm_id: UUID, after_seq: int, limit: int) -> list[StoredRecord]:
    return [
        StoredRecord(r.seq, r.kind, r.payload, r.recorded_at, r.prev_hash, r.hash)
        for r in repository.records(session, realm_id, after_seq, limit)
    ]


def unanchored(session: Session) -> list[AuditCheckpoint]:
    return repository.unanchored(session)


def realms_needing_checkpoint(session: Session, created_before: datetime) -> list[UUID]:
    return repository.realms_needing_checkpoint(session, created_before)


def record_anchor_result(
    session: Session, realm_id: UUID, seq: int, error: str | None, now: datetime
) -> AuditCheckpoint:
    checkpoint = repository.checkpoint(session, realm_id, seq)
    if checkpoint is None:
        raise AssertionError("контрольная точка исчезла между транзакциями")
    checkpoint.anchored_at = None if error else now
    checkpoint.anchor_error = error
    return checkpoint
