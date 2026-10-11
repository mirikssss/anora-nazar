"""Внешние источники через шлюз банка на синтетике: самозапрет и очередь бюро; факты бюро, карт, ИНПС и реестра
юрлиц уходят в узел событиями."""

from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy.orm import Session

from bank_sim.modules.outbox import service as outbox
from bank_sim.modules.sources import repository
from bank_sim.modules.sources.domain import (
    CompanyProfile,
    SourceProfile,
    bureau_report,
    card_spending,
    company_record,
    inps_contributions,
)

# Факт источника → (источник, тип сущности) в конверте события; типы сущностей — как в истории мира.
FACT_SOURCES = {
    "bureau.report": ("bank-sim.bureau", "bureau_report"),
    "cards.spending": ("bank-sim.cards", "card_spending"),
    "inps.contributions": ("bank-sim.inps", "inps_contributions"),
    "registry.company": ("bank-sim.registry", "company"),
}


def self_ban_status(session: Session, realm_id: UUID, pinfl: str) -> Literal["active", "none"]:
    record = repository.self_ban(session, realm_id, pinfl)
    return "active" if record is not None and record.status == "active" else "none"


def set_self_ban(session: Session, realm_id: UUID, pinfl: str, status: str, now: datetime) -> None:
    repository.set_self_ban(session, realm_id, pinfl, status, now)


def bureau_status(session: Session, realm_id: UUID, pinfl: str, now: datetime) -> Literal["free", "blocked"]:
    lock = repository.bureau_lock(session, realm_id, pinfl)
    return "blocked" if lock is not None and lock.locked_until > now else "free"


def lock_after_disbursement(session: Session, realm_id: UUID, pinfl: str, now: datetime, hours: int) -> None:
    repository.set_bureau_lock(session, realm_id, pinfl, now + timedelta(hours=hours))


def _emit_fact(
    session: Session, realm_id: UUID, fact_type: str, entity_id: str, payload: BaseModel, now: datetime
) -> None:
    source, entity_type = FACT_SOURCES[fact_type]
    outbox.emit(
        session,
        realm_id,
        source=source,
        type_=fact_type,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_version=None,
        payload=payload.model_dump(mode="json"),
        occurred_at=now,
    )


def report_profile(session: Session, realm_id: UUID, pinfl: str, profile: SourceProfile, now: datetime) -> None:
    """Ответы источников по клиенту, как их получает банк перед вызовом узла: каждый — событием в узел."""
    today = now.date()
    request_id = f"{pinfl}:{uuid4().hex[:12]}"
    if profile.bureau is not None:
        _emit_fact(session, realm_id, "bureau.report", request_id, bureau_report(pinfl, profile.bureau, today), now)
    if profile.cards is not None:
        _emit_fact(session, realm_id, "cards.spending", request_id, card_spending(pinfl, profile.cards, today), now)
    if profile.inps is not None:
        payload = inps_contributions(pinfl, profile.inps, today)
        _emit_fact(session, realm_id, "inps.contributions", request_id, payload, now)


def report_company(session: Session, realm_id: UUID, inn: str, profile: CompanyProfile, now: datetime) -> None:
    """Запись реестра юрлиц при первом появлении компании в заявке."""
    _emit_fact(session, realm_id, "registry.company", inn, company_record(inn, profile, now.date()), now)
