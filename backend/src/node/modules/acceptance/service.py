"""Т5: акт приёмки до разрешения на оплату поставщику (Блок 4, «Т5 · Акт приёмки вызывает сомнения»)."""

from datetime import datetime

from sqlalchemy.orm import Session

from node.modules.applications import service as applications
from node.modules.cases import service as cases
from node.modules.cases.service import CaseContext, DecisionSummary
from node.modules.index import service as index
from node.modules.ingest import service as ingest
from node.modules.permits import service as permits
from node.modules.policy.domain import PolicyBundle
from node.modules.realms.domain import RealmContext
from shared.contracts.facts import AcceptanceAct
from shared.errors import NotFoundError, ValidationFailedError

ACT = "program.acceptance_act"


def guard(
    session: Session,
    ctx: CaseContext,
    bundle: PolicyBundle,
    realm: RealmContext,
    external_id: str,
    act_id: str,
    now: datetime,
) -> None:
    """Сомнительный акт — удержание оплаты и дело; само разрешение затем откажет по действующему удержанию."""
    rules = bundle.policy.acceptance
    if rules is None:
        return
    payload = ingest.latest_fact(session, realm, ACT, now, entity_id=act_id)
    if payload is None:
        raise ValidationFailedError("acceptance_act_unknown", "Акт приёмки узлу неизвестен")
    act = AcceptanceAct.model_validate(payload)
    if act.application_id != external_id:
        raise ValidationFailedError("acceptance_act_mismatch", "Акт приёмки относится к другой заявке")
    app_id = applications.find_id(session, realm.id, external_id)
    if app_id is None:
        raise NotFoundError("application_not_found", "Заявка неизвестна узлу")
    same_day = ingest.acts_by_signer(session, realm, act.signer_id, act.signed_on.isoformat(), now)
    reasons = []
    if same_day >= rules.batch_acts_per_signer_day:
        evidence = {"signer_id": act.signer_id, "acts_that_day": same_day, "threshold": rules.batch_acts_per_signer_day}
        reasons.append(bundle.reason("F3_BATCH_ACCEPTANCE_ACTS", [evidence], "yellow"))
    stops = index.stop_listed(session, realm, app_id, ["supplier"], now)
    if stops:
        reasons.append(bundle.reason("PRODUCT_CONFIRMED_CASE_IDENTIFIER", [m.model_dump() for m in stops], "red"))
    if not reasons:
        return
    app = applications.lock(session, {app_id})[app_id]
    if app.latest_decision_id is None:
        return
    basis = [r.model_dump(mode="json") for r in reasons]
    permits.place_hold(
        session,
        realm_id=realm.id,
        application_id=app_id,
        external_id=external_id,
        decision_id=app.latest_decision_id,
        required_check=rules.required_check,
        basis=basis,
        config=ctx.node,
        now=now,
    )
    snapshot = applications.snapshot_of(session, app, app.current_version)[0]
    summary = DecisionSummary(
        decision_id=app.latest_decision_id,
        version=app.current_version,
        point="T5",
        level="red" if stops else "yellow",
        action=rules.required_check,
        channel=snapshot.channel,
        amount=act.invoice_amount,
        term_months=snapshot.loan.term_months,
        branch_id=snapshot.branch_id,
        employee_id=snapshot.employee_id,
        reasons=basis,
        features={},
        unavailable_sources=[],
        leading_typology="F3",
        strategy="application",
        linked_applications=[],
    )
    cases.open_for(session, ctx, realm, app_id, external_id, summary, now)
