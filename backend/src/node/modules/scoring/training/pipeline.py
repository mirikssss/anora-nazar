"""Прогон обучения на контуре: выборка на дату среза, модели по конфигурации, версии в тень, отчёт качества."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from node.modules.consortium.service import NetworkContext
from node.modules.features import service as features
from node.modules.labels import service as labels
from node.modules.policy.domain import Policy
from node.modules.quality import point_in_time
from node.modules.quality import service as quality
from node.modules.realms.domain import RealmContext
from node.modules.scoring import repository
from node.modules.scoring.models import ModelVersion
from node.modules.scoring.training import dataset
from node.modules.scoring.training.config import NETWORK_GROUP, NETWORK_SUFFIX, ModelSpec, TrainingConfig
from node.modules.scoring.training.train import train_spec
from shared.errors import ConfigurationError


@dataclass(frozen=True)
class TrainingResult:
    versions: list[ModelVersion]
    report: dict[str, Any]


def specs(cfg: TrainingConfig) -> list[ModelSpec]:
    """При f2_mode=per_channel общая F2 заменяется двумя моделями — по одной на канал и точку.

    Модель с группой network обучается двумя вариантами на тех же окнах: локальный (узел без сети) и «-net».
    """
    split = []
    for spec in cfg.models:
        if spec.typology != "F2" or cfg.f2_mode == "shared":
            split.append(spec)
            continue
        split += [
            spec.model_copy(update={"name": f"{spec.name}-online", "points": ["T1"], "calibrate_by_channel": False}),
            spec.model_copy(update={"name": f"{spec.name}-program", "points": ["T4"], "calibrate_by_channel": False}),
        ]
    result = []
    for spec in split:
        if not spec.uses_network:
            result.append(spec)
            continue
        local = [g for g in spec.groups if g != NETWORK_GROUP]
        result += [
            spec.model_copy(update={"groups": local}),
            spec.model_copy(update={"name": f"{spec.name}{NETWORK_SUFFIX}"}),
        ]
    return result


def run(
    session: Session,
    realm: RealmContext,
    cfg: TrainingConfig,
    policy: Policy,
    index_key: bytes,
    now: datetime,
    network: NetworkContext | None = None,
) -> TrainingResult:
    if cfg.feature_set != features.config().version:
        raise ConfigurationError(f"Обучение настроено на {cfg.feature_set}, а узел считает {features.config().version}")
    cutoff = labels.latest_received(session, realm.visible_ids) or now
    examples = dataset.build(session, realm, cutoff, policy, index_key, network, now)
    versions, summaries = [], []
    for spec in specs(cfg):
        version, summary = train_spec(examples, spec, cfg, cutoff, now, features.config().timezone)
        summaries.append(summary)
        if version is not None:
            version.realm_id = None if not realm.is_sandbox else realm.id
            repository.add(session, version)
            versions.append(version)
    timing = point_in_time.check(session, realm, policy, index_key, cfg.point_in_time_sample, cfg.seed)
    report = {
        "point_in_time": timing.as_dict(),
        "config": cfg.version,
        "feature_set": cfg.feature_set,
        "cutoff": cutoff.isoformat(),
        "examples": len(examples),
        "f2_mode": cfg.f2_mode,
        "models": summaries,
    }
    quality.save(session, realm.id, report, now)
    session.flush()  # выпуск в той же транзакции ищет версии по id
    return TrainingResult(versions=versions, report=report)
