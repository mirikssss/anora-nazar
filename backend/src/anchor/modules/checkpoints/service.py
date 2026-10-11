"""Приём контрольных точек: подпись узла проверяется, прежние точки не перезаписываются."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from anchor.modules.checkpoints import repository
from anchor.modules.checkpoints.models import Checkpoint
from anchor.modules.checkpoints.schemas import CheckpointIn
from shared.crypto.signing import Verifier
from shared.errors import ConflictError, ValidationFailedError


def accept(session: Session, body: CheckpointIn, verifier: Verifier, now: datetime) -> Checkpoint:
    payload = {
        "realm_id": str(body.realm_id),
        "seq": body.seq,
        "merkle_root": body.merkle_root,
        "head_hash": body.head_hash,
        "created_at": body.created_at.isoformat(),
    }
    if body.key_id != verifier.key_id or not verifier.is_valid(payload, body.signature):
        raise ValidationFailedError("bad_signature", "Подпись контрольной точки не сходится с ключом узла")
    existing = repository.get(session, body.realm_id, body.seq)
    if existing is not None:
        if existing.merkle_root != body.merkle_root:
            raise ConflictError("checkpoint_rewrite", "Для этой позиции журнала якорь уже хранит другой корень")
        return existing
    checkpoint = Checkpoint(
        realm_id=body.realm_id,
        seq=body.seq,
        merkle_root=body.merkle_root,
        head_hash=body.head_hash,
        signature=body.signature,
        key_id=body.key_id,
        created_at=body.created_at,
        received_at=now,
    )
    repository.add(session, checkpoint)
    return checkpoint


def list_for_realm(session: Session, realm_id: UUID) -> list[Checkpoint]:
    return repository.for_realm(session, realm_id)
