"""Платформа программ: справочники мира (помощники хокимов, поставщики) и акты приёмки — факт для Т5."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from bank_sim.modules.conveyor import service as conveyor
from bank_sim.modules.outbox import service as outbox
from bank_sim.modules.program_platform import repository
from bank_sim.modules.program_platform.models import AcceptanceActRecord, ProgramHelper, ProgramSupplier
from bank_sim.modules.program_platform.schemas import ActIn
from shared.contracts.facts import AcceptanceAct
from shared.errors import ConflictError, ValidationFailedError

SOURCE = "bank-sim.program-platform"
ACT_EVENT = "program.acceptance_act"
ACT_ENTITY = "acceptance_act"
HELPER_ROLE = "helper"


def upsert_world(session: Session, helpers: list[dict[str, Any]], suppliers: list[dict[str, Any]]) -> None:
    """Справочники синтетического мира — те же помощники и поставщики, что в истории узла."""
    repository.upsert(session, ProgramHelper, helpers)
    repository.upsert(session, ProgramSupplier, suppliers)


def helpers(session: Session, district: str | None = None) -> list[ProgramHelper]:
    return repository.helpers(session, district)


def suppliers(session: Session, district: str | None = None, category: str | None = None) -> list[ProgramSupplier]:
    return repository.suppliers(session, district, category)


def create_act(session: Session, realm_id: UUID, body: ActIn, now: datetime) -> AcceptanceActRecord:
    """Акт приёмки программной заявки; в узел уходит событием вместе с записью."""
    app = conveyor.get(session, realm_id, body.application_id)
    if app.channel != "program":
        raise ValidationFailedError("not_program_application", "Акт приёмки — только по программной заявке")
    if app.status == "cancelled":
        raise ConflictError("application_cancelled", "Заявка отменена")
    if body.signed_on > now.date():
        raise ValidationFailedError("act_signed_in_future", "Дата подписания акта ещё не наступила")
    if body.signer_role == HELPER_ROLE and repository.helper(session, body.signer_id) is None:
        raise ValidationFailedError("unknown_helper", "Такого помощника хокима нет в справочнике")
    act = AcceptanceActRecord(
        id=f"ACT-{uuid4().hex[:12].upper()}",
        realm_id=realm_id,
        application_id=app.external_id,
        signer_id=body.signer_id,
        signer_role=body.signer_role,
        signed_on=body.signed_on,
        invoice_amount=body.invoice_amount,
        created_at=now,
    )
    repository.add_act(session, act)
    payload = AcceptanceAct(
        act_id=act.id,
        application_id=act.application_id,
        signer_id=body.signer_id,
        signer_role=body.signer_role,
        signed_on=body.signed_on,
        invoice_amount=body.invoice_amount,
    )
    outbox.emit(
        session,
        realm_id,
        source=SOURCE,
        type_=ACT_EVENT,
        entity_type=ACT_ENTITY,
        entity_id=act.id,
        entity_version=None,
        payload=payload.model_dump(mode="json"),
        occurred_at=now,
    )
    return act


def acts(session: Session, realm_id: UUID, application_id: str | None = None) -> list[AcceptanceActRecord]:
    return repository.acts(session, realm_id, application_id)


def find_act(session: Session, realm_id: UUID, act_id: str) -> AcceptanceActRecord | None:
    return repository.act(session, realm_id, act_id)
