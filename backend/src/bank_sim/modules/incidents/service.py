"""Жалобы клиентов и документы органов: запись в песочнице и событие incident.recorded для меток узла."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from bank_sim.modules.incidents import repository
from bank_sim.modules.incidents.models import Incident
from bank_sim.modules.outbox import service as outbox
from shared.contracts.facts import IncidentRecorded

SOURCE = "bank-sim.incidents"
EVENT = "incident.recorded"
ENTITY = "incident"


def record(session: Session, realm_id: UUID, body: IncidentRecorded, now: datetime) -> Incident:
    incident = Incident(
        id=f"INC-{uuid4().hex[:12].upper()}",
        realm_id=realm_id,
        kind=body.kind,
        typology=body.typology,
        result=body.result,
        application_ids=list(body.application_ids),
        case_key=body.case_key,
        created_at=now,
    )
    repository.add(session, incident)
    outbox.emit(
        session,
        realm_id,
        source=SOURCE,
        type_=EVENT,
        entity_type=ENTITY,
        entity_id=incident.id,
        entity_version=None,
        payload=body.model_dump(mode="json"),
        occurred_at=now,
    )
    return incident


def list_for_realm(session: Session, realm_id: UUID) -> list[Incident]:
    return repository.list_for_realm(session, realm_id)
