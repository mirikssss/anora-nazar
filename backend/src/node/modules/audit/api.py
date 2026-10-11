"""Роутер модуля: записи журнала, контрольная точка по кнопке риск-менеджера, проверка целостности."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from node.deps import Ctx, Realm, require_permission
from node.modules.audit import anchoring, service
from node.modules.audit.schemas import AnchorMismatchOut, BreakOut, CheckpointOut, RecordOut, VerificationOut
from node.modules.identity.domain import StaffPrincipal

router = APIRouter(prefix="/v1/audit", tags=["Журнал"])
Viewer = Annotated[StaffPrincipal, Depends(require_permission("audit.view"))]
Verifier = Annotated[StaffPrincipal, Depends(require_permission("audit.verify"))]
MAX_PAGE = 500


@router.get("/records", response_model=list[RecordOut])
def records(
    ctx: Ctx,
    realm: Realm,
    _: Viewer,
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 100,
) -> list[RecordOut]:
    with ctx.db.transaction() as session:
        return [
            RecordOut(
                seq=r.seq, kind=r.kind, payload=r.payload, recorded_at=r.recorded_at, prev_hash=r.prev_hash, hash=r.hash
            )
            for r in service.page(session, realm.id, after_seq, limit)
        ]


@router.post("/checkpoints", response_model=CheckpointOut | None)
def create_checkpoint(ctx: Ctx, realm: Realm, _: Verifier) -> CheckpointOut | None:
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        checkpoint = service.create_checkpoint(session, realm.id, ctx.signer, now)
    if checkpoint is None:
        return None
    error = anchoring.send(ctx.anchor, checkpoint)
    with ctx.db.transaction() as session:
        stored = service.record_anchor_result(session, realm.id, checkpoint.seq, error, ctx.clock.now())
        return CheckpointOut(
            seq=stored.seq,
            merkle_root=stored.merkle_root,
            created_at=stored.created_at,
            anchored=stored.anchored_at is not None,
            anchor_error=stored.anchor_error,
        )


@router.get("/verify", response_model=VerificationOut)
def verify(ctx: Ctx, realm: Realm, _: Verifier) -> VerificationOut:
    roots = anchoring.anchored_roots(ctx.anchor, realm.id)
    with ctx.db.transaction() as session:
        report = service.verify(session, realm.id, roots or {})
    brk, mismatch = report.first_break, report.anchor_mismatch
    return VerificationOut(
        intact=report.intact and roots is not None,
        records_checked=report.records_checked,
        first_break=None if brk is None else BreakOut(seq=brk.seq, kind=brk.kind, problem=brk.problem),
        checkpoints_checked=report.checkpoints_checked,
        anchor_mismatch=None if mismatch is None else AnchorMismatchOut(seq=mismatch.seq, problem=mismatch.problem),
        anchor_reachable=roots is not None,
    )
