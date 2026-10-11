"""Обзор риск-менеджера по контуру: что видно из записей решений и очередей дел."""

from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from node.modules.cases import service as cases
from node.modules.decisions import service as decisions
from node.modules.realms.domain import RealmContext
from node.modules.risk.domain import RiskConfig, psi


def overview(session: Session, realm: RealmContext, config: RiskConfig) -> dict[str, Any]:
    latest = decisions.latest_assessment_at(session, realm.visible_ids)
    if latest is None:
        return {"latest": None, "levels": [], "queues": cases.queue_counts(session, realm), "drift": []}
    levels = decisions.level_counts(session, realm.visible_ids, latest - timedelta(days=config.days))
    recent_from = latest - timedelta(days=config.drift_recent_days)
    reference_from = recent_from - timedelta(days=config.drift_reference_days)
    rows = decisions.feature_values(session, realm.visible_ids, reference_from, config.drift_features)
    drift = []
    for name in config.drift_features:
        reference = [float(v[name]) for at, v in rows if at <= recent_from and v.get(name) is not None]
        recent = [float(v[name]) for at, v in rows if at > recent_from and v.get(name) is not None]
        drift.append(
            {
                "feature": name,
                "psi": psi(reference, recent, config.drift_bins, config.psi_floor),
                "reference": len(reference),
                "recent": len(recent),
            }
        )
    return {"latest": latest, "levels": levels, "queues": cases.queue_counts(session, realm), "drift": drift}
