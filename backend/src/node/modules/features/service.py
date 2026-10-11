"""Расчёт признаков заявки на момент as_of: только факты с received_at ≤ as_of. Один код для решения и обучения."""

from dataclasses import dataclass
from datetime import datetime
from functools import cache
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from node.modules.features.domain import (
    FEATURE_SET_VERSION,
    Facts,
    FeatureConfig,
    FeatureVector,
    Point,
    Value,
    assemble,
    load_feature_config,
    zone1_features,
    zone2_features,
    zone3_features,
)
from node.modules.index import service as index
from node.modules.index.domain import GroupView, subject_key
from node.modules.ingest import service as ingest
from node.modules.policy.domain import Policy
from node.modules.realms.domain import RealmContext
from shared.contracts.application import ApplicationSnapshot
from shared.contracts.facts import BureauReport, CardSpending, CompanyRecord, InpsContributions, SessionSummary


@dataclass(frozen=True)
class FeatureResult:
    vector: FeatureVector
    graph: GroupView
    signals: dict[str, Value]


@cache
def config() -> FeatureConfig:
    return load_feature_config(FEATURE_SET_VERSION)


def _parse[T: BaseModel](model: type[T], payload: dict[str, Any] | None) -> T | None:
    return None if payload is None else model.model_validate(payload)


def _facts(
    session: Session, realm: RealmContext, snapshot: ApplicationSnapshot, subject: str, as_of: datetime
) -> Facts:
    def personal(type_: str) -> dict[str, Any] | None:
        return ingest.latest_fact(session, realm, type_, as_of, subject_key=subject)

    def company(inn: str | None) -> CompanyRecord | None:
        if inn is None:
            return None
        return _parse(CompanyRecord, ingest.latest_fact(session, realm, "registry.company", as_of, entity_id=inn))

    return Facts(
        session=_parse(SessionSummary, personal("session.summary")) if snapshot.channel == "online" else None,
        cards=_parse(CardSpending, personal("cards.spending")),
        bureau=_parse(BureauReport, personal("bureau.report")),
        inps=_parse(InpsContributions, personal("inps.contributions")),
        supplier=company(snapshot.program.supplier_inn if snapshot.program else None),
        employer=company(snapshot.applicant.employer_inn),
    )


def _first_credit_share(
    session: Session, realm: RealmContext, members: tuple[str, ...], as_of: datetime
) -> float | None:
    """Доля «первый кредит» среди участников группы идентичности, у кого есть ответ бюро."""
    if len(members) < 2:
        return None
    found = ingest.latest_facts_by_subject(session, realm, "bureau.report", list(members), as_of)
    answers = [BureauReport.model_validate(p) for p in found.values()]
    if not answers:
        return None
    return round(sum(1 for b in answers if b.active_loans + b.closed_loans == 0) / len(answers), 4)


def compute(
    session: Session,
    realm: RealmContext,
    application_id: UUID,
    point: Point,
    snapshot: ApplicationSnapshot,
    as_of: datetime,
    policy: Policy,
    index_key: bytes,
) -> FeatureResult:
    cfg = config()
    subject = subject_key(index_key, snapshot.applicant.pinfl)
    facts = _facts(session, realm, snapshot, subject, as_of)
    view = index.group_view(session, realm, application_id, as_of, policy)
    parts = zone2_features(view, _first_credit_share(session, realm, view.member_subjects, as_of))
    if point == "T1":
        devices = index.device_subjects(session, realm, application_id, as_of, cfg.zone1.device_shared_window_days)
        parts |= zone1_features(snapshot, as_of, facts, devices, cfg)
    pricing = cfg.zone3.pricing
    levels = [(level.scope == "district", level.days) for level in pricing.levels]
    concentration = cfg.zone3.concentration
    roles = index.concentrations(
        session,
        realm,
        application_id,
        as_of,
        index.ConcentrationParams(
            window_days=concentration.window_days,
            prior_weight=concentration.prior_weight,
            prior_windows=concentration.prior_windows,
            helper_window_days=cfg.zone3.helper_burst_window_days,
        ),
    )
    prices = index.comparable_prices(session, realm, application_id, snapshot, levels, as_of)
    parts |= zone3_features(snapshot, facts, prices, roles, as_of, cfg)
    vector, signals = assemble(point, snapshot, parts, facts)
    return FeatureResult(vector=vector, graph=view, signals=signals)
