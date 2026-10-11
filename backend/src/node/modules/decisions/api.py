"""Роутер модуля: Т1 и Т4 — оценка заявки; запись решения и её воспроизведение."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from node.deps import Ctx, IdempotencyKey, Realm, require_permission, require_scope
from node.modules.decisions import service
from node.modules.decisions.schemas import (
    AssessmentIn,
    ComparisonIn,
    ComparisonOut,
    DecisionOut,
    DecisionRecordOut,
    ReplayOut,
)
from node.modules.identity.domain import StaffPrincipal, SystemPrincipal
from node.modules.policy.reasons import Reason
from shared.contracts.transfers import TransferRecommendationIn

router = APIRouter(prefix="/v1", tags=["Решения"])
Conveyor = Annotated[SystemPrincipal, Depends(require_scope("assessments"))]
Viewer = Annotated[StaffPrincipal, Depends(require_permission("decisions.view"))]


@router.post("/assessments", response_model=DecisionOut)
def assess(body: AssessmentIn, ctx: Ctx, realm: Realm, key: IdempotencyKey, _: Conveyor) -> DecisionOut:
    as_of = ctx.clock.now()
    assessing = ctx.assessing()
    result = ctx.db.run(lambda session: service.assess(session, assessing, realm, body, key, as_of))
    return DecisionOut.model_validate(result)


@router.get("/decisions/{decision_id}", response_model=DecisionRecordOut)
def get_decision(decision_id: UUID, ctx: Ctx, realm: Realm, _: Viewer) -> DecisionRecordOut:
    with ctx.db.transaction() as session:
        d = service.get_record(session, realm, decision_id)
        return DecisionRecordOut(
            decision_id=d.id,
            application_version=d.application_version,
            point=d.point,
            as_of=d.as_of,
            record=d.record,
            record_hash=d.record_hash,
        )


@router.get("/decisions/{decision_id}/replay", response_model=ReplayOut)
def replay(decision_id: UUID, ctx: Ctx, realm: Realm, _: Viewer) -> ReplayOut:
    with ctx.db.transaction() as session:
        return ReplayOut.model_validate(service.replay(session, realm, decision_id, ctx.policies))


@router.post("/decisions/{decision_id}/comparison", response_model=ComparisonOut)
def compare(decision_id: UUID, body: ComparisonIn, ctx: Ctx, realm: Realm, _: Viewer) -> ComparisonOut:
    with ctx.db.transaction() as session:
        result = service.compare(
            session, realm, decision_id, ctx.policies, ctx.models, body.policy_version, body.model_version_ids
        )
        return ComparisonOut.model_validate(result)


Transfers = Annotated[SystemPrincipal, Depends(require_scope("transfers"))]


class TransferRecommendationOut(BaseModel):
    recommendation_id: UUID
    level: str
    recommended_action: str
    reasons: list[Reason]


@router.post("/transfers/recommendations", response_model=TransferRecommendationOut)
def recommend_transfer(
    body: TransferRecommendationIn, ctx: Ctx, realm: Realm, _: Transfers
) -> TransferRecommendationOut:
    """Т3: рекомендация транзакционному антифроду банка; решение о переводе принимает он (ревью A)."""
    now = ctx.clock.now()
    assessing = ctx.assessing()
    result = ctx.db.run(lambda session: service.recommend_transfer(session, assessing, realm, body, now))
    return TransferRecommendationOut.model_validate(result)
