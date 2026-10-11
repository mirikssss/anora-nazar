"""Реестр моделей в контуре: какая версия действует, какие идут в тени; скоринг вектора признаков.

Модель запускается только с совпадающим контрактом признаков. Выпуск в песочнице действует только в ней.
"""

from dataclasses import dataclass, field
from threading import Lock
from uuid import UUID

import lightgbm as lgb
import numpy as np
from sqlalchemy.orm import Session

from node.modules.features.domain import FeatureVector
from node.modules.policy.domain import ModelPolicy
from node.modules.realms.domain import RealmContext
from node.modules.scoring import repository
from node.modules.scoring.domain import (
    ModelScore,
    ScoringOutcome,
    calibrate,
    channel_of,
    contract_matches,
    feature_row,
    top_contributions,
)
from node.modules.scoring.models import ModelVersion


@dataclass
class ModelCache:
    """Загруженные бустеры по id версии: версия неизменна, поэтому кэш не устаревает."""

    _boosters: dict[UUID, lgb.Booster] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def booster(self, version: ModelVersion) -> lgb.Booster:
        with self._lock:
            found = self._boosters.get(version.id)
            if found is None:
                found = lgb.Booster(model_str=version.artifact)
                self._boosters[version.id] = found
            return found


def active_versions(session: Session, realm: RealmContext) -> dict[str, ModelVersion]:
    """Действующая версия каждой модели: последний подтверждённый выпуск; выпуск песочницы важнее мира."""
    chosen: dict[str, tuple[bool, UUID]] = {}
    for release in repository.approved_releases(session, realm.visible_ids):
        own = release.realm_id == realm.id and realm.is_sandbox
        current = chosen.get(release.model_name)
        if current is None or own or not current[0]:
            chosen[release.model_name] = (own, release.model_version_id)
    versions = {v.id: v for v in repository.get_many(session, [vid for _own, vid in chosen.values()])}
    return {name: versions[vid] for name, (_own, vid) in chosen.items()}


def shadow_versions(session: Session, active: dict[str, ModelVersion]) -> list[ModelVersion]:
    """Тень — самая новая версия каждой модели, обученная после действующей и ещё не выпущенная."""
    latest: dict[str, ModelVersion] = {}
    for version in repository.all_versions(session):
        current = active.get(version.name)
        if version.name in latest or (current is not None and version.created_at <= current.created_at):
            continue
        latest[version.name] = version
    return list(latest.values())


def score(cache: ModelCache, version: ModelVersion, vector: FeatureVector, top: int) -> ModelScore:
    names = list(version.feature_names)
    row = np.array([feature_row(names, vector.values)])
    booster = cache.booster(version)
    raw = float(booster.predict(row)[0])
    contributions = [float(c) for c in booster.predict(row, pred_contrib=True)[0][:-1]]
    return ModelScore(
        model_version_id=str(version.id),
        name=version.name,
        typology=version.typology,
        probability=calibrate(raw, version.calibration, channel_of(vector.values)),
        contributions=top_contributions(names, vector.values, contributions, top),
    )


def _missing(policy: ModelPolicy, vector: FeatureVector, scores: list[ModelScore]) -> list[str]:
    expected = policy.expected_typologies.get(vector.point, []) if vector.point else []
    return sorted(set(expected) - {s.typology for s in scores})


def evaluate(
    session: Session,
    cache: ModelCache,
    realm: RealmContext,
    vector: FeatureVector,
    policy: ModelPolicy | None,
) -> ScoringOutcome:
    active = active_versions(session, realm)
    point = vector.point or ""

    def fits(v: ModelVersion) -> bool:
        return contract_matches(v.points, v.feature_set_version, point, vector.set_version)

    compatible = [v for v in active.values() if fits(v)]
    checked = [str(v.id) for v in active.values()]
    if policy is None or not compatible:
        return ScoringOutcome(
            status="no_model",
            reason="contract_mismatch" if active else "registry_empty",
            checked_models=checked,
            scores=[],
        )
    top = policy.top_contributions
    scores = [score(cache, v, vector, top) for v in sorted(compatible, key=lambda v: v.name)]
    missing = _missing(policy, vector, scores)
    shadow = [score(cache, v, vector, top) for v in shadow_versions(session, active) if fits(v)]
    return ScoringOutcome(
        status="scored",
        reason="partial" if missing else None,
        checked_models=checked,
        scores=scores,
        missing_typologies=missing,
        shadow=sorted(shadow, key=lambda s: s.name),
    )


def rescore(
    session: Session, cache: ModelCache, model_ids: list[UUID], vector: FeatureVector, policy: ModelPolicy
) -> ScoringOutcome:
    """Сравнение версий: те же сохранённые признаки через выбранные версии моделей."""
    versions = [
        v
        for v in repository.get_many(session, model_ids)
        if contract_matches(v.points, v.feature_set_version, vector.point or "", vector.set_version)
    ]
    scores = [score(cache, v, vector, policy.top_contributions) for v in sorted(versions, key=lambda v: v.name)]
    if not scores:
        return ScoringOutcome(status="no_model", reason="contract_mismatch", checked_models=[], scores=[])
    missing = _missing(policy, vector, scores)
    return ScoringOutcome(
        status="scored",
        reason="partial" if missing else None,
        checked_models=[str(v.id) for v in versions],
        scores=scores,
        missing_typologies=missing,
    )


def versions_with_status(session: Session, realm: RealmContext) -> list[tuple[ModelVersion, str]]:
    active = active_versions(session, realm)
    active_ids = {v.id for v in active.values()}
    shadow_ids = {v.id for v in shadow_versions(session, active)}
    return [
        (v, "active" if v.id in active_ids else "shadow" if v.id in shadow_ids else "retired")
        for v in repository.all_versions(session)
    ]
