"""Роутер модуля: действующая политика контура, предложения порогов и их утверждение вторым подписантом."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from node.deps import Ctx, Realm, require_permission
from node.modules.identity.domain import StaffPrincipal
from node.modules.policy import service
from node.modules.policy.models import PolicyProposal

router = APIRouter(prefix="/v1/policy", tags=["Политика"])
Viewer = Annotated[StaffPrincipal, Depends(require_permission("decisions.view"))]
Proposer = Annotated[StaffPrincipal, Depends(require_permission("policy.propose"))]
Approver = Annotated[StaffPrincipal, Depends(require_permission("policy.approve"))]


class EditableThreshold(BaseModel):
    """Порог (число) или переключатель (true/false, например сеть кредиторов)."""

    path: str
    value: bool | float


class ProposalOut(BaseModel):
    proposal_id: UUID
    base_version: str
    changes: dict[str, bool | float]
    reason: str
    proposed_by: str
    proposed_at: datetime
    approved_by: str | None
    approved_at: datetime | None
    resulting_version: str | None


class PolicyOverviewOut(BaseModel):
    active_version: str
    policy_hash: str
    thresholds: list[EditableThreshold]
    proposals: list[ProposalOut]


class ProposalIn(BaseModel):
    changes: dict[str, bool | float] = Field(min_length=1, max_length=20)
    reason: str = Field(min_length=3, max_length=2000)


def _value(content: dict[str, Any], path: str) -> bool | float | None:
    node: Any = content
    for part in path.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    if isinstance(node, bool):
        return node
    return float(node) if isinstance(node, int | float) else None


def _out(p: PolicyProposal) -> ProposalOut:
    return ProposalOut(
        proposal_id=p.id,
        base_version=p.base_version,
        changes=p.changes,
        reason=p.reason,
        proposed_by=p.proposed_by,
        proposed_at=p.proposed_at,
        approved_by=p.approved_by,
        approved_at=p.approved_at,
        resulting_version=p.resulting_version,
    )


@router.get("", response_model=PolicyOverviewOut)
def overview(ctx: Ctx, realm: Realm, _: Viewer) -> PolicyOverviewOut:
    with ctx.db.transaction() as session:
        bundle, proposals = service.overview(session, ctx.policies, realm)
        content = ctx.policies.raw(bundle.policy.version)
        thresholds = [
            EditableThreshold(path=path, value=value)
            for path in ctx.config.policy.editable
            if (value := _value(content, path)) is not None
        ]
        return PolicyOverviewOut(
            active_version=bundle.policy.version,
            policy_hash=bundle.policy_hash,
            thresholds=thresholds,
            proposals=[_out(p) for p in proposals],
        )


@router.post("/proposals", response_model=ProposalOut, status_code=201)
def propose(body: ProposalIn, ctx: Ctx, realm: Realm, staff: Proposer) -> ProposalOut:
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        proposal = service.propose(
            session, ctx.policies, realm, body.changes, body.reason, staff.user_code, ctx.config.policy.editable, now
        )
        return _out(proposal)


@router.post("/proposals/{proposal_id}/approval", response_model=ProposalOut)
def approve(proposal_id: UUID, ctx: Ctx, realm: Realm, staff: Approver) -> ProposalOut:
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        return _out(
            service.approve(session, ctx.policies, realm, proposal_id, staff.user_code, ctx.config.policy.editable, now)
        )
