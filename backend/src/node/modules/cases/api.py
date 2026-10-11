"""Роутер модуля: очереди, карточка дела, граф, взять в работу, решение по участнику, исход, ретро-поиск."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from node.deps import Ctx, Realm, get_principal
from node.modules.cases import service
from node.modules.cases.models import Case, CaseApplication
from node.modules.cases.schemas import (
    ApplicantView,
    BenignOut,
    CaseApplicationBrief,
    CaseApplicationOut,
    CaseDetailOut,
    CaseGraphOut,
    CaseListItem,
    GraphEdgeOut,
    GraphNodeOut,
    HoldOut,
    OutcomeIn,
    ParticipantDecisionIn,
    ReasonOut,
    RetroMatch,
    RetroSearchOut,
    ScriptQuestion,
    TimelineEntry,
)
from node.modules.identity.domain import Principal, StaffPrincipal
from shared.errors import ForbiddenError

router = APIRouter(prefix="/v1/cases", tags=["Дела"])


def staff_only(principal: Annotated[Principal, Depends(get_principal)]) -> StaffPrincipal:
    if not isinstance(principal, StaffPrincipal):
        raise ForbiddenError("staff_only", "Дела ведут сотрудники узла")
    return principal


Staff = Annotated[StaffPrincipal, Depends(staff_only)]


def _mask(value: str) -> str:
    return "•" * max(len(value) - 4, 0) + value[-4:]


def _brief(m: CaseApplication) -> CaseApplicationBrief:
    s = m.summary
    return CaseApplicationBrief(
        application_id=m.external_id,
        point=s["point"],
        channel=s["channel"],
        level=s["level"],
        amount=s["amount"],
        risk_cost_estimate=s.get("risk_cost_estimate"),
    )


def _list_item(case: Case, members: list[CaseApplication]) -> CaseListItem:
    costs: list[float] = [
        float(m.summary["risk_cost_estimate"]) for m in members if m.summary.get("risk_cost_estimate") is not None
    ]
    return CaseListItem(
        case_id=str(case.id),
        queue=case.queue,
        zone=case.zone,
        strategy=case.strategy,
        status=case.status,
        assignee=case.assignee,
        due_at=case.due_at,
        escalated_at=case.escalated_at,
        created_at=case.created_at,
        risk_cost_estimate=max(costs, default=None),
        applications=[_brief(m) for m in members],
    )


@router.get("", response_model=list[CaseListItem])
def queue(ctx: Ctx, realm: Realm, staff: Staff, name: Annotated[str, Query(alias="queue")]) -> list[CaseListItem]:
    with ctx.db.transaction() as session:
        return [_list_item(c, members) for c, members in service.queue(session, realm, name, staff)]


@router.get("/{case_id}", response_model=CaseDetailOut)
def detail(case_id: UUID, ctx: Ctx, realm: Realm, staff: Staff, full_pii: bool = False) -> CaseDetailOut:
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        view = service.detail(session, ctx.case_context(), realm, case_id, staff, full_pii, now)
        case = view.case
        config = ctx.cases_config
        applications = []
        for m in view.members:
            s, applicant = m.summary, view.snapshots[m.application_id]["applicant"]
            applications.append(
                CaseApplicationOut(
                    application_id=m.external_id,
                    status=view.statuses[m.application_id],
                    point=s["point"],
                    channel=s["channel"],
                    level=s["level"],
                    action=s["action"],
                    amount=s["amount"],
                    term_months=s["term_months"],
                    risk_cost_estimate=s.get("risk_cost_estimate"),
                    reasons=[ReasonOut.model_validate(r) for r in s["reasons"]],
                    features=s["features"],
                    unavailable_sources=s["unavailable_sources"],
                    holds=[HoldOut.model_validate(h) for h in view.holds[m.application_id]],
                    applicant=ApplicantView(
                        pinfl=applicant["pinfl"] if full_pii else _mask(applicant["pinfl"]),
                        phone=applicant["phone"] if full_pii else _mask(applicant["phone"]),
                        address=applicant.get("address") if full_pii else None,
                        full=full_pii,
                    ),
                    decision=m.decision,
                    role=m.role,
                    basis=m.basis,
                    decided_by=m.decided_by,
                    decided_at=m.decided_at,
                )
            )
        script = (
            [
                ScriptQuestion(code=q.code, answers=[a.code for a in q.answers])
                for q in ctx.verification_config.questions
            ]
            if case.queue == "online"
            else []
        )
        return CaseDetailOut(
            case_id=str(case.id),
            queue=case.queue,
            zone=case.zone,
            strategy=case.strategy,
            status=case.status,
            assignee=case.assignee,
            due_at=case.due_at,
            escalated_at=case.escalated_at,
            outcome=case.outcome,
            created_at=case.created_at,
            closed_at=case.closed_at,
            applications=applications,
            benign=[BenignOut.model_validate(b) for b in view.benign],
            checklist_items=config.checklists.get(str(case.zone), []),
            call_script=script,
            allowed_outcomes=list(config.outcomes),
            participant_actions=list(config.participant_actions),
            participant_roles=list(config.participant_roles),
            timeline=[
                TimelineEntry(at=e.at, actor=e.actor, kind=e.kind, payload=e.payload, audit_seq=e.audit_seq)
                for e in view.events
            ],
        )


@router.get("/{case_id}/graph", response_model=CaseGraphOut)
def graph(case_id: UUID, ctx: Ctx, realm: Realm, staff: Staff) -> CaseGraphOut:
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        case, nodes, edges, apps = service.graph(session, ctx.case_context(), realm, case_id, staff, now)
        return CaseGraphOut(
            case_id=str(case.id),
            nodes=[
                GraphNodeOut(
                    id=n.id,
                    type=n.type,
                    display=apps[n.id][0] if n.id in apps else n.display,
                    application_id=apps[n.id][0] if n.id in apps else None,
                    level=apps[n.id][1] if n.id in apps else None,
                )
                for n in nodes
            ],
            edges=[GraphEdgeOut(source=e.source, target=e.target, type=e.type, rare=e.rare) for e in edges],
        )


@router.post("/{case_id}/assignment", response_model=CaseListItem)
def assign(case_id: UUID, ctx: Ctx, realm: Realm, staff: Staff) -> CaseListItem:
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        case = service.assign(session, realm, case_id, staff, now)
        return _list_item(case, service.members(session, case.id))


@router.post("/{case_id}/applications/{application_id}/decision", response_model=CaseListItem)
def decide(
    case_id: UUID, application_id: str, body: ParticipantDecisionIn, ctx: Ctx, realm: Realm, staff: Staff
) -> CaseListItem:
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        app_id = service.application_in_case(session, realm, case_id, application_id)
        service.decide_participant(
            session, ctx.case_context(), realm, case_id, app_id, body.action, body.role, body.basis, staff, now
        )
        case = service.get(session, realm, case_id)
        return _list_item(case, service.members(session, case.id))


@router.post("/{case_id}/outcome", response_model=CaseListItem)
def outcome(case_id: UUID, body: OutcomeIn, ctx: Ctx, realm: Realm, staff: Staff) -> CaseListItem:
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        case = service.close(
            session,
            ctx.case_context(),
            realm,
            case_id,
            body.outcome,
            body.checklist,
            body.answers,
            body.note,
            staff,
            now,
        )
        return _list_item(case, service.members(session, case.id))


@router.post("/{case_id}/retro-search", response_model=RetroSearchOut)
def retro_search(case_id: UUID, ctx: Ctx, realm: Realm, staff: Staff) -> RetroSearchOut:
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        matches = service.retro_search(session, ctx.case_context(), realm, case_id, staff, now)
        return RetroSearchOut(
            case_id=str(case_id), matches=[RetroMatch(application_id=a, shared=k) for a, k in matches]
        )
