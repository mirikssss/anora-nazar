"""Сценарии дел: открытие по решению, очереди, карточка с уликами и безобидными объяснениями, граф, решения по
участникам, исход и разрешённые им действия, Т6 после закрытия, эскалация по сроку.

Каждое действие пишется одной записью и в ленту дела, и в журнал контура.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from node.modules.applications import service as applications
from node.modules.audit import service as audit
from node.modules.cases import repository
from node.modules.cases.domain import (
    NOT_LABELED_ROLES,
    TYPOLOGY_BY_ZONE,
    ZONE_BY_TYPOLOGY,
    CasesConfig,
    Outcome,
    OutcomeRule,
    ParticipantAction,
    Strategy,
    due_at,
    queue_for,
)
from node.modules.cases.models import Case, CaseApplication, CaseEvent
from node.modules.consortium import service as consortium
from node.modules.consortium.service import NetworkContext
from node.modules.identity.domain import StaffPrincipal
from node.modules.index import service as index
from node.modules.index.domain import GraphEdge, GraphNode
from node.modules.labels import service as labels
from node.modules.outbox import service as outbox
from node.modules.permits import service as permits
from node.modules.policy.domain import Policy
from node.modules.policy.service import PolicyRegistry
from node.modules.realms.domain import RealmContext
from node.settings import NodeConfig
from shared.contracts.network import TokenKind
from shared.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError

SYSTEM = "system"
QUEUE_CHECK = {"online": "pause_for_call", "group": "internal_review"}  # удержание, которое ставит решение по делу
QUEUE_PERMISSIONS = {
    "online": ("cases.online.view", "cases.online.decide"),
    "group": ("cases.group.view", "cases.group.decide"),
}
# решение по заявке в деле — своё право очереди; роль участника — отдельное право (Блок 4, роли и права)
HOLD_PERMISSIONS = {"online": "pauses.lift", "group": "holds.manage"}
ASSIGN_ROLE_PERMISSION = "participants.assign_role"
LABEL_SOURCE = {"online": "antifraud_center", "group": "internal_control"}


@dataclass(frozen=True)
class CaseContext:
    config: CasesConfig
    node: NodeConfig
    policy: Policy
    network: NetworkContext | None = None
    policies: PolicyRegistry | None = None  # действующая политика контура: включена ли сеть


@dataclass(frozen=True)
class DecisionSummary:
    """Что дело берёт из решения узла: уровень, причины, признаки и связи на момент оценки."""

    decision_id: UUID
    version: int
    point: str
    level: str | None
    action: str
    channel: str
    amount: int
    term_months: int
    branch_id: str
    employee_id: str | None
    reasons: list[dict[str, Any]]
    features: dict[str, Any]
    unavailable_sources: list[str]
    leading_typology: str | None
    strategy: Strategy
    linked_applications: list[UUID]

    def as_json(self) -> dict[str, Any]:
        costs = [
            e.get("risk_cost_estimate", 0)
            for r in self.reasons
            for e in r.get("evidence", [])
            if r.get("code", "").startswith("MODEL_")
        ]
        return {
            "decision_id": str(self.decision_id),
            "version": self.version,
            "point": self.point,
            "level": self.level,
            "action": self.action,
            "channel": self.channel,
            "amount": self.amount,
            "term_months": self.term_months,
            "branch_id": self.branch_id,
            "employee_id": self.employee_id,
            "risk_cost_estimate": max(costs, default=None),
            "reasons": self.reasons,
            "features": self.features,
            "unavailable_sources": self.unavailable_sources,
        }


def _log(session: Session, case: Case, actor: str, kind: str, payload: dict[str, Any], now: datetime) -> None:
    seq = audit.append(
        session, case.realm_id, f"case.{kind}", {"case_id": str(case.id), "actor": actor, **payload}, now
    )
    repository.add(session, CaseEvent(case_id=case.id, actor=actor, kind=kind, payload=payload, audit_seq=seq, at=now))


def _attach(
    session: Session, case: Case, app_id: UUID, external_id: str, summary: DecisionSummary, now: datetime
) -> None:
    found = repository.member(session, case.id, app_id)
    if found is None:
        repository.add(
            session,
            CaseApplication(
                case_id=case.id,
                application_id=app_id,
                external_id=external_id,
                summary=summary.as_json(),
                decision=None,
                role=None,
                basis=None,
                decided_by=None,
                decided_at=None,
                added_at=now,
            ),
        )
        _log(session, case, SYSTEM, "application_added", {"application_id": external_id, "level": summary.level}, now)
    else:
        found.summary = summary.as_json()
    case.updated_at = now


def open_for(
    session: Session,
    ctx: CaseContext,
    realm: RealmContext,
    app_id: UUID,
    external_id: str,
    summary: DecisionSummary,
    now: datetime,
) -> Case | None:
    """Дело по решению: очередь — по действию, зона — по типологии ведущей причины. Связанная заявка группы
    присоединяется к уже открытому делу этой группы."""
    queue = queue_for(ctx.config, summary.action)
    if queue is None:
        return None
    zone = ZONE_BY_TYPOLOGY.get(summary.leading_typology or "", 1 if queue == "online" else 2)
    case = repository.open_case_with(session, realm.id, queue, [app_id, *summary.linked_applications])
    if case is None:
        case = Case(
            id=uuid4(),
            realm_id=realm.id,
            queue=queue,
            zone=zone,
            strategy=summary.strategy,
            status="open",
            assignee=None,
            due_at=due_at(ctx.config, queue, now),
            escalated_at=None,
            outcome=None,
            checklist={},
            created_at=now,
            updated_at=now,
            closed_at=None,
        )
        repository.add(session, case)
        session.flush()
        _log(session, case, SYSTEM, "opened", {"queue": queue, "zone": zone, "strategy": summary.strategy}, now)
    _attach(session, case, app_id, external_id, summary, now)
    return case


def refresh(session: Session, app_id: UUID, external_id: str, summary: DecisionSummary, now: datetime) -> None:
    """Новая оценка заявки из открытого дела обновляет её сводку в деле."""
    for case in repository.open_cases_of(session, app_id):
        _attach(session, case, app_id, external_id, summary, now)


def _require(staff: StaffPrincipal, case: Case, decide: bool) -> None:
    view, act = QUEUE_PERMISSIONS[case.queue]
    if (act if decide else view) not in staff.permissions:
        raise ForbiddenError("permission_required", f"Нужно право «{act if decide else view}»")


def _require_permission(staff: StaffPrincipal, permission: str) -> None:
    if permission not in staff.permissions:
        raise ForbiddenError("permission_required", f"Нужно право «{permission}»")


def _own_division(staff: StaffPrincipal, members: list[CaseApplication]) -> None:
    """Сотрудник филиала не ведёт дела своего подразделения (Блок 4, ограничения ролей)."""
    if staff.branch_id and any(m.summary.get("branch_id") == staff.branch_id for m in members):
        raise ForbiddenError("own_division", "Дела своего подразделения ведёт другой сотрудник")


def _case(session: Session, realm: RealmContext, case_id: UUID, *, lock: bool = False) -> Case:
    case = repository.get_visible(session, realm.id, case_id, lock=lock)
    if case is None:
        raise NotFoundError("case_not_found", "Дело не найдено")
    return case


def queue(
    session: Session, realm: RealmContext, name: str, staff: StaffPrincipal
) -> list[tuple[Case, list[CaseApplication]]]:
    """Очередь по оценочной стоимости риска (Блок 4): сначала дела с наибольшим возможным ущербом."""
    if name not in QUEUE_PERMISSIONS:
        raise ValidationFailedError("unknown_queue", "Очередь — online или group")
    if QUEUE_PERMISSIONS[name][0] not in staff.permissions:
        raise ForbiddenError("permission_required", f"Нужно право «{QUEUE_PERMISSIONS[name][0]}»")
    cases = repository.in_queue(session, realm.id, name)
    members = repository.members(session, [c.id for c in cases])
    by_case: dict[UUID, list[CaseApplication]] = {}
    for m in members:
        by_case.setdefault(m.case_id, []).append(m)

    def loss(case: Case) -> float:
        return max((m.summary.get("risk_cost_estimate") or 0 for m in by_case.get(case.id, [])), default=0)

    return [(c, by_case.get(c.id, [])) for c in sorted(cases, key=lambda c: (-loss(c), c.due_at))]


@dataclass(frozen=True)
class CaseView:
    case: Case
    members: list[CaseApplication]
    statuses: dict[UUID, str]
    holds: dict[UUID, list[dict[str, Any]]]
    snapshots: dict[UUID, dict[str, Any]]
    events: list[CaseEvent]
    benign: list[dict[str, Any]]


def detail(
    session: Session,
    ctx: CaseContext,
    realm: RealmContext,
    case_id: UUID,
    staff: StaffPrincipal,
    full_pii: bool,
    now: datetime,
) -> CaseView:
    case = _case(session, realm, case_id)
    _require(staff, case, decide=False)
    members = repository.members(session, [case.id])
    if full_pii:
        if "pii.full.view" not in staff.permissions:
            raise ForbiddenError("permission_required", "Нужно право «pii.full.view»")
        _log(session, case, staff.user_code, "pii_viewed", {"applications": [m.external_id for m in members]}, now)
    apps = {m.application_id: applications.get_by_id(session, m.application_id) for m in members}
    snapshots = {
        app_id: applications.snapshot_of(session, app, app.current_version)[0].model_dump(mode="json")
        for app_id, app in apps.items()
    }
    return CaseView(
        case=case,
        members=members,
        statuses={app_id: app.status for app_id, app in apps.items()},
        holds={
            m.application_id: [
                {"hold_id": str(h.id), "required_check": h.required_check, "created_at": h.created_at.isoformat()}
                for h in permits.active_holds(session, m.application_id)
            ]
            for m in members
        },
        snapshots=snapshots,
        events=repository.events(session, case.id),
        benign=benign_explanations(session, ctx, realm, members, now),
    )


def benign_explanations(
    session: Session, ctx: CaseContext, realm: RealmContext, members: list[CaseApplication], now: datetime
) -> list[dict[str, Any]]:
    """Автоматические безобидные объяснения (Блок 2, шаг 3): домохозяйство, зарплатный проект, программная партия.
    Это описание фактов для проверяющего, а не решение."""
    rules, found = ctx.config.benign, []
    ids = {m.application_id for m in members}
    attrs = index.case_attributes(session, ids, ["address", "phone", "employer", "helper", "supplier", "employee"], now)
    by_kind: dict[tuple[str, str], set[UUID]] = {}
    subjects: dict[tuple[str, str], set[str]] = {}
    for app, kind, key, _display, subject in attrs:
        by_kind.setdefault((kind, key), set()).add(app)
        subjects.setdefault((kind, key), set()).add(subject)
    households = [pair for pair, apps in by_kind.items() if pair[0] == "address" and len(subjects[pair]) > 1]
    if households:
        found.append({"code": "household", "evidence": {"shared_addresses": len(households)}})
    features = {m.application_id: m.summary.get("features", {}) for m in members}
    payroll = rules.payroll_project
    for (kind, _key), apps in by_kind.items():
        ages = [features[a].get("employer_age_days") for a in apps]
        if (
            kind == "employer"
            and len(apps) >= payroll.min_applicants
            and all(age is not None and age >= payroll.employer_min_age_days for age in ages)
        ):
            found.append({"code": "payroll_project", "evidence": {"applications": len(apps)}})
            break
    batch = rules.program_batch
    cohorts: dict[tuple[tuple[str, str], ...], set[UUID]] = {}
    for app in ids:
        trio = tuple(
            sorted(p for p, apps in by_kind.items() if app in apps and p[0] in ("helper", "supplier", "employee"))
        )
        cohorts.setdefault(trio, set()).add(app)
    for trio, apps in cohorts.items():
        values = [features[a] for a in apps]
        if (
            len(trio) == 3
            and len(apps) > 1
            and all((v.get("price_robust_z") or 0) <= batch.max_price_robust_z for v in values)
            and all((v.get("supplier_age_days") or 0) >= batch.supplier_min_age_days for v in values)
        ):
            found.append({"code": "program_batch", "evidence": {"applications": len(apps)}})
            break
    return found


def graph(
    session: Session, ctx: CaseContext, realm: RealmContext, case_id: UUID, staff: StaffPrincipal, now: datetime
) -> tuple[Case, list[GraphNode], list[GraphEdge], dict[str, tuple[str, str | None]]]:
    """Подграф дела и подписи узлов-заявок: внешний id и текущий уровень."""
    case = _case(session, realm, case_id)
    _require(staff, case, decide=False)
    members = {m.application_id for m in repository.members(session, [case.id])}
    nodes, edges = index.case_graph(session, realm, members, now, ctx.policy)
    labels_by_app = {}
    for node in nodes:
        if node.application_id is not None:
            app = applications.get_by_id(session, UUID(node.application_id))
            labels_by_app[node.id] = (app.external_id, app.assessment_level)
    return case, nodes, edges, labels_by_app


def assign(session: Session, realm: RealmContext, case_id: UUID, staff: StaffPrincipal, now: datetime) -> Case:
    case = _case(session, realm, case_id, lock=True)
    _require(staff, case, decide=True)
    _own_division(staff, repository.members(session, [case.id]))
    if case.status == "closed":
        raise ConflictError("case_closed", "Дело уже закрыто")
    case.assignee, case.status, case.updated_at = staff.user_code, "in_progress", now
    _log(session, case, staff.user_code, "assigned", {}, now)
    return case


def decide_participant(
    session: Session,
    ctx: CaseContext,
    realm: RealmContext,
    case_id: UUID,
    app_id: UUID,
    action: ParticipantAction,
    role: str | None,
    basis: str,
    staff: StaffPrincipal,
    now: datetime,
) -> CaseApplication:
    """Решение по одной заявке группы — удержание, отпуск или отказ — со своим основанием (Блок 4)."""
    case = _case(session, realm, case_id, lock=True)
    _require(staff, case, decide=True)
    members = repository.members(session, [case.id])
    _own_division(staff, members)
    member = next((m for m in members if m.application_id == app_id), None)
    if member is None:
        raise NotFoundError("case_application_not_found", "Заявки нет в этом деле")
    if case.status == "closed":
        raise ConflictError("case_closed", "Дело уже закрыто")
    if role is not None and role not in ctx.config.participant_roles:
        raise ValidationFailedError("unknown_role", "Неизвестная роль участника")
    _require_permission(staff, HOLD_PERMISSIONS[case.queue])
    if role is not None:
        _require_permission(staff, ASSIGN_ROLE_PERMISSION)
    app = applications.lock(session, {app_id})[app_id]
    if action == "release":
        permits.release_holds(
            session,
            realm_id=realm.id,
            application_id=app_id,
            external_id=member.external_id,
            checks=None,
            actor=staff.user_code,
            reason=basis,
            config=ctx.node,
            now=now,
        )
    elif action == "refuse":
        applications.refuse(app, now)
    else:
        permits.place_hold(
            session,
            realm_id=realm.id,
            application_id=app_id,
            external_id=member.external_id,
            decision_id=UUID(member.summary["decision_id"]),
            required_check=QUEUE_CHECK[case.queue],
            basis=[{"code": "CASE_DECISION", "case_id": str(case.id), "basis": basis}],
            config=ctx.node,
            now=now,
        )
    member.decision, member.role, member.basis = action, role, basis
    member.decided_by, member.decided_at = staff.user_code, now
    payload = {"application_id": member.external_id, "action": action, "role": role, "basis": basis}
    _log(session, case, staff.user_code, "participant_decided", payload, now)
    return member


def close(
    session: Session,
    ctx: CaseContext,
    realm: RealmContext,
    case_id: UUID,
    outcome: Outcome,
    checklist: dict[str, bool],
    answers: dict[str, str],
    note: str,
    staff: StaffPrincipal,
    now: datetime,
) -> Case:
    """Исход дела и только разрешённые им действия: заявка, стоп-лист, метка; затем пересчёт связанных (Т6)."""
    case = _case(session, realm, case_id, lock=True)
    _require(staff, case, decide=True)
    members = repository.members(session, [case.id])
    _own_division(staff, members)
    if case.status == "closed":
        raise ConflictError("case_closed", "Дело уже закрыто")
    allowed = set(ctx.config.checklists.get(str(case.zone), []))
    if set(checklist) - allowed:
        raise ValidationFailedError("unknown_checklist_item", "В чек-листе зоны нет такого пункта")
    rule = ctx.config.outcomes[outcome]
    undecided = [m for m in members if m.decision is None]
    locked = applications.lock(session, {m.application_id for m in undecided})
    for m in undecided:
        app = locked[m.application_id]
        if rule.application == "refuse":
            m.decision, m.decided_by, m.decided_at = "refuse", staff.user_code, now
            applications.refuse(app, now)
        elif rule.application == "cancel":
            applications.cancel(app, now)
        elif rule.application == "release":
            m.decision, m.decided_by, m.decided_at = "release", staff.user_code, now
            permits.release_holds(
                session,
                realm_id=realm.id,
                application_id=m.application_id,
                external_id=m.external_id,
                checks=None,
                actor=staff.user_code,
                reason=outcome,
                config=ctx.node,
                now=now,
            )
    participants = [m for m in members if outcome != "confirmed_fraud" or m.role not in NOT_LABELED_ROLES]
    stopped = 0
    if rule.stop_list:
        ids = {m.application_id for m in participants}
        stopped = index.add_to_stop_list(session, realm.id, ids, ctx.config.stop_list_kinds, case.id, now)
    labeled = 0
    if rule.label is not None:
        labeled = labels.record_case_outcome(
            session,
            realm.id,
            [m.application_id for m in participants],
            typology=TYPOLOGY_BY_ZONE[case.zone] if rule.label == "positive" else None,
            kind=rule.label,
            source=LABEL_SOURCE[case.queue],
            case_key=str(case.id),
            event_id=uuid4(),
            now=now,
        )
    recalculated = _recalculate_linked(session, ctx, realm, case, {m.application_id for m in members}, now)
    shared = _report_to_network(session, ctx, realm, case, rule, outcome, members, participants, now)
    case.status, case.outcome, case.checklist = "closed", outcome, {"items": checklist, "answers": answers}
    case.closed_at = case.updated_at = now
    _log(
        session,
        case,
        staff.user_code,
        "closed",
        {
            "outcome": outcome,
            "note": note,
            "checklist": checklist,
            "answers": answers,
            "stop_list": stopped,
            "labels": labeled,
            "recalculated": recalculated,
            "network_tokens": shared,
        },
        now,
    )
    return case


def _report_to_network(
    session: Session,
    ctx: CaseContext,
    realm: RealmContext,
    case: Case,
    rule: OutcomeRule,
    outcome: str,
    members: list[CaseApplication],
    participants: list[CaseApplication],
    now: datetime,
) -> int:
    """Результат проверки — в сеть, только пока она включена и только по исходу (Блок 4).

    Подтверждённый фрод — идентификаторы участников, кроме жертв и посторонних: телефон, устройство, карта,
    ПИНФЛ организатора, поставщик схемы. Подтверждённое воздействие — только карта-получатель мошенника.
    """
    if rule.network is None or ctx.network is None or ctx.policies is None:
        return 0
    if not consortium.enabled(ctx.policies.for_realm(session, realm).policy):
        return 0
    sources = members if rule.network == "recipient_card" else participants
    card_keys = [
        key for _kind, key in index.attribute_keys(session, {m.application_id for m in sources}, ["card"], now)
    ]
    items: list[tuple[TokenKind, str]] = []
    if rule.network == "fraudster_identifiers":
        for member in participants:
            app = applications.get_by_id(session, member.application_id)
            snapshot = applications.snapshot_of(session, app, app.current_version)[0]
            items.append(("phone", snapshot.applicant.phone))
            if snapshot.applicant.device_id is not None:
                items.append(("device", snapshot.applicant.device_id))
            if member.role == "organizer":
                items.append(("pinfl", snapshot.applicant.pinfl))
            if snapshot.program is not None and (case.zone == 3 or member.role == "involved_supplier"):
                items.append(("supplier_inn", snapshot.program.supplier_inn))
    return consortium.report_confirmed(
        session,
        ctx.network,
        realm,
        f"case:{case.id}",
        TYPOLOGY_BY_ZONE[case.zone],
        outcome,
        sorted(set(items)),
        card_keys,
        now,
    )


def _recalculate_linked(
    session: Session, ctx: CaseContext, realm: RealmContext, case: Case, members: set[UUID], now: datetime
) -> list[str]:
    """Т6: закрытое дело меняет картину связей — открытые связанные заявки сразу помечаются «нужна новая оценка»,
    до пересчёта разрешение на их проводку не выдаётся."""
    kinds = ["pinfl", *ctx.policy.index.identity_kinds, *ctx.config.stop_list_kinds]
    linked = index.sharing_applications(session, realm, members, kinds, ctx.policy.index.window_days, now)
    targets = applications.open_ids(session, realm.id, set(linked), now)
    locked = applications.lock(session, targets)
    cause = {"case_id": str(case.id), "outcome": case.outcome, "received_at": now.isoformat()}
    marked = applications.mark_for_reassessment(session, realm.id, set(locked), cause, now)
    for app_id in marked:
        event = {"application_id": locked[app_id].external_id, "cause": cause, "kinds": sorted(linked[app_id])}
        outbox.enqueue(session, ctx.node.outbox, realm.id, "application.reassessment_required", event, now)
    return [locked[a].external_id for a in marked]


def retro_search(
    session: Session, ctx: CaseContext, realm: RealmContext, case_id: UUID, staff: StaffPrincipal, now: datetime
) -> list[tuple[str, list[str]]]:
    """Ретро-поиск Т6: выданные за 12 месяцев кредиты с общими идентификаторами заявок дела."""
    case = _case(session, realm, case_id)
    if "retro_search.run" not in staff.permissions:
        raise ForbiddenError("permission_required", "Нужно право «retro_search.run»")
    members = {m.application_id for m in repository.members(session, [case.id])}
    days = ctx.config.retro_search_months * 30
    issued = permits.executed_applications(session, realm.visible_ids, now - timedelta(days=days))
    issued |= labels.issued_application_ids(session, realm.visible_ids)
    kinds = ["pinfl", "phone", "device", "address", "card"]
    found = index.sharing_applications(session, realm, members, kinds, days, now)
    matches = [
        (applications.get_by_id(session, app).external_id, sorted(kinds_))
        for app, kinds_ in found.items()
        if app in issued
    ]
    _log(session, case, staff.user_code, "retro_search", {"matches": len(matches)}, now)
    return sorted(matches)


def escalate_overdue(session: Session, now: datetime) -> int:
    """Срок разбора прошёл — дело эскалируется руководителю (Блок 4, «Сроки и эскалации»)."""
    cases = repository.overdue(session, now)
    for case in cases:
        case.status, case.escalated_at, case.updated_at = "escalated", now, now
        _log(session, case, SYSTEM, "escalated", {"due_at": case.due_at.isoformat()}, now)
    return len(cases)


def queue_counts(session: Session, realm: RealmContext) -> dict[str, int]:
    return repository.counts_by_queue(session, realm.id)


def verified(session: Session, app_id: UUID, version: int) -> bool:
    """Связь этой версии заявки уже проверена и заявка отпущена: результат проверки хранится (Блок 4),
    повторного удержания по той же версии нет; новая версия проверяется заново."""
    return repository.released(session, app_id, version)


def get(session: Session, realm: RealmContext, case_id: UUID) -> Case:
    return _case(session, realm, case_id)


def members(session: Session, case_id: UUID) -> list[CaseApplication]:
    return repository.members(session, [case_id])


def application_in_case(session: Session, realm: RealmContext, case_id: UUID, external_id: str) -> UUID:
    app_id = applications.find_id(session, realm.id, external_id)
    if app_id is None or repository.member(session, case_id, app_id) is None:
        raise NotFoundError("case_application_not_found", "Заявки нет в этом деле")
    return app_id
