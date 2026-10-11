"""Обучение LightGBM по паре «типология × точки»: разбиение по времени и по группам, калибровка, отчёт качества.

Отчёт сравнивает модель с базовым уровнем «правила и граф без ML», поштучную модель с моделью + граф,
общую F2 с раздельными по каналам (ревью D) и показывает нагрузку худших дней (ревью C).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import lightgbm as lgb
import numpy as np

from node.modules.features.catalog import PASSPORTS
from node.modules.features.domain import FEATURE_SET_VERSION
from node.modules.quality.domain import metrics, predictive_equality, threshold_at_share, worst_days
from node.modules.scoring.domain import calibrate, feature_row
from node.modules.scoring.models import ModelVersion
from node.modules.scoring.training.calibrate import calibration
from node.modules.scoring.training.config import ModelSpec, TrainingConfig
from node.modules.scoring.training.dataset import Example, age_band, gender


@dataclass(frozen=True)
class Split:
    train: list[Example]
    calibration: list[Example]
    test: list[Example]
    unlabeled_test: list[Example]
    isolation: dict[str, int]


@dataclass(frozen=True)
class Fitted:
    booster: lgb.Booster
    names: list[str]
    calibration: dict[str, Any]


def feature_names(spec: ModelSpec, exclude_groups: frozenset[str] = frozenset()) -> list[str]:
    return [
        name
        for name, p in PASSPORTS.items()
        if p.group in spec.groups and p.group not in exclude_groups and set(p.points) & set(spec.points)
    ]


def target(example: Example, typology: str, weak_weight: float) -> tuple[int, float] | None:
    """Позитив — подтверждённая метка этой типологии; негатив — любая другая метка; без меток — не учим."""
    if not example.labels:
        return None
    if any(label.kind == "positive" and label.typology == typology for label in example.labels):
        return 1, 1.0
    weak_only = all(label.kind == "weak_negative" for label in example.labels)
    return 0, weak_weight if weak_only else 1.0


def groups(examples: list[Example]) -> dict[UUID, UUID]:
    """Связные группы заявок по общим идентификаторам (человек, телефон, устройство, адрес, дело) — union-find."""
    parent: dict[UUID, UUID] = {e.application_id: e.application_id for e in examples}

    def root(node: UUID) -> UUID:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    owner: dict[str, UUID] = {}
    for e in examples:
        for key in e.identifiers:
            other = owner.setdefault(key, e.application_id)
            parent[root(e.application_id)] = root(other)
    return {app: root(app) for app in parent}


def split(examples: list[Example], spec: ModelSpec, cfg: TrainingConfig, *, all_test_groups: bool = False) -> Split:
    """Старшие месяцы — обучение, затем калибровка, последние — тест; границы времени — внутри канала, метки
    каналов созревают по-разному. Строго: в обучение не попадает ни одна заявка из одной группы с мошенниками
    теста (общий человек, телефон, устройство, адрес или дело) и ни один поставщик тестовых схем.
    all_test_groups=True — изоляция от групп всех заявок теста, включая честные (проверка на пределе строгости)."""
    scoped = [e for e in examples if e.point in spec.points]
    labeled = [e for e in scoped if target(e, spec.typology, cfg.weak_negative_weight) is not None]
    if not labeled:
        return Split([], [], [], [], {})
    phase = {}
    for channel in {e.channel for e in labeled}:
        own = [e for e in labeled if e.channel == channel]
        train_end = own[int(len(own) * cfg.split.train)].as_of
        cal_end = own[min(int(len(own) * (cfg.split.train + cfg.split.calibration)), len(own) - 1)].as_of
        phase[channel] = (train_end, cal_end)

    def stage(e: Example) -> str:
        train_end, cal_end = phase[e.channel]
        return "train" if e.as_of < train_end else "calibration" if e.as_of < cal_end else "test"

    test = [e for e in labeled if stage(e) == "test"]
    labeled_ids = {e.application_id for e in labeled}
    group_of = groups(scoped)
    frauds = [e for e in test if target(e, spec.typology, cfg.weak_negative_weight) == (1, 1.0)]
    test_groups = {group_of[e.application_id] for e in (test if all_test_groups else frauds)}
    fraud_suppliers = {e.supplier for e in frauds if e.supplier}

    def isolated(e: Example) -> bool:
        return group_of[e.application_id] not in test_groups and e.supplier not in fraud_suppliers

    before = [e for e in labeled if stage(e) != "test"]
    kept = [e for e in before if isolated(e)]
    sizes: dict[UUID, int] = {}
    for app in group_of.values():
        sizes[app] = sizes.get(app, 0) + 1
    return Split(
        train=[e for e in kept if stage(e) == "train"],
        calibration=[e for e in kept if stage(e) == "calibration"],
        test=test,
        unlabeled_test=[
            e
            for e in scoped
            if e.application_id not in labeled_ids and e.channel in phase and e.as_of >= phase[e.channel][1]
        ],
        isolation={
            "excluded_from_training": len(before) - len(kept),
            "test_groups": len(test_groups),
            "largest_group": max(sizes.values(), default=0),
            "held_out_fraud_suppliers": len(fraud_suppliers),
        },
    )


def _xy(examples: list[Example], names: list[str], spec: ModelSpec, cfg: TrainingConfig) -> tuple[Any, Any, Any]:
    targets = [target(e, spec.typology, cfg.weak_negative_weight) for e in examples]
    x = np.array([feature_row(names, e.values) for e in examples], dtype=float).reshape(len(examples), len(names))
    y = np.array([t[0] if t else 0 for t in targets], dtype=float)
    w = np.array([t[1] if t else 0.0 for t in targets], dtype=float)
    return x, y, w


def _channels(examples: list[Example]) -> np.ndarray:
    return np.array([e.channel for e in examples])


def fit(data: Split, spec: ModelSpec, cfg: TrainingConfig, names: list[str]) -> Fitted | None:
    x, y, w = _xy(data.train, names, spec, cfg)
    if int(y.sum()) < cfg.min_positives:
        return None
    booster = lgb.train(dict(cfg.lightgbm), lgb.Dataset(x, label=y, weight=w, feature_name=names, free_raw_data=True))
    calibration_set, source = data.calibration, "calibration"
    if int(_xy(calibration_set, names, spec, cfg)[1].sum()) < cfg.min_calibration_positives:
        calibration_set, source = data.train, "train"
    cx, cy, _ = _xy(calibration_set, names, spec, cfg)
    curve = calibration(
        np.asarray(booster.predict(cx)),
        cy,
        _channels(calibration_set),
        by_channel=spec.calibrate_by_channel,
        min_positives=cfg.min_calibration_positives,
        source=source,
    )
    return Fitted(booster=booster, names=names, calibration=curve)


def raw_scores(fitted: Fitted, examples: list[Example]) -> np.ndarray:
    if not examples:
        return np.array([])
    x = np.array([feature_row(fitted.names, e.values) for e in examples], dtype=float)
    return np.asarray(fitted.booster.predict(x))


def predict(fitted: Fitted, examples: list[Example]) -> np.ndarray:
    raw = raw_scores(fitted, examples)
    return np.array([calibrate(float(v), fitted.calibration, e.channel) for v, e in zip(raw, examples, strict=True)])


def _metrics(
    y: np.ndarray, ranking: np.ndarray, cfg: TrainingConfig, probabilities: np.ndarray | None
) -> dict[str, Any]:
    return metrics(
        y,
        ranking,
        review_shares=cfg.review_shares,
        fpr=cfg.fpr,
        probabilities=probabilities,
        bootstrap=(cfg.bootstrap_resamples, int(cfg.lightgbm["seed"])),
    )


def _evaluate(fitted: Fitted, examples: list[Example], spec: ModelSpec, cfg: TrainingConfig) -> dict[str, Any]:
    _, y, _ = _xy(examples, fitted.names, spec, cfg)
    return _metrics(y, raw_scores(fitted, examples), cfg, predict(fitted, examples))


def _by_channel(fitted: Fitted, examples: list[Example], spec: ModelSpec, cfg: TrainingConfig) -> dict[str, Any]:
    return {
        channel: _evaluate(fitted, [e for e in examples if e.channel == channel], spec, cfg)
        for channel in ("online", "program")
        if any(e.channel == channel for e in examples)
    }


def _local_day(moment: datetime, timezone: str) -> Any:
    return moment.astimezone(ZoneInfo(timezone)).date()


def report(
    spec: ModelSpec,
    data: Split,
    fitted: Fitted,
    variants: dict[str, Fitted | None],
    cfg: TrainingConfig,
    timezone: str,
) -> dict[str, Any]:
    _, y, _ = _xy(data.test, fitted.names, spec, cfg)
    ranking = raw_scores(fitted, data.test)
    baseline = np.array([e.rules_score for e in data.test])
    threshold = threshold_at_share(ranking, cfg.review_share)
    per_application = variants.get("per_application")
    ablation: dict[str, Any] = {
        "rules_graph_baseline": _metrics(y, baseline, cfg, None),
        "per_application": _evaluate(per_application, data.test, spec, cfg) if per_application else None,
        "with_graph": _evaluate(fitted, data.test, spec, cfg),
        # сеть кредиторов подключается в И4; тот же тест и тот же бюджет проверки
        "with_graph_and_network": {"status": "network_not_connected"},
    }
    on_day = data.test[-1].as_of.date() if data.test else None
    load_set = data.test + data.unlabeled_test
    load_scores = raw_scores(fitted, load_set)
    importance = sorted(
        zip(fitted.names, fitted.booster.feature_importance(importance_type="gain"), strict=True),
        key=lambda item: -item[1],
    )
    result: dict[str, Any] = {
        "model": spec.name,
        "typology": spec.typology,
        "points": spec.points,
        "data": {
            "train": len(data.train),
            "calibration": len(data.calibration),
            "test": len(data.test),
            "positives_train": int(_xy(data.train, fitted.names, spec, cfg)[1].sum()),
            "positives_test": int(y.sum()),
            "test_from": data.test[0].as_of.isoformat() if data.test else None,
            "test_to": data.test[-1].as_of.isoformat() if data.test else None,
            "calibration_source": fitted.calibration["source"],
            **data.isolation,
        },
        "test": ablation["with_graph"],
        "by_channel": _by_channel(fitted, data.test, spec, cfg),
        "ablation": ablation,
        "fairness": {
            "threshold": round(threshold, 6),
            "gender": predictive_equality(y, ranking, [gender(e.pinfl) for e in data.test], threshold),
            "age_band": predictive_equality(
                y, ranking, [age_band(e.pinfl, on_day, cfg.age_bands) for e in data.test] if on_day else [], threshold
            ),
        },
        "load": worst_days([_local_day(e.as_of, timezone) for e in load_set], load_scores > threshold),
        "top_features": [{"feature": n, "gain": round(float(g), 2)} for n, g in importance[:10] if g > 0],
    }
    separate: dict[str, Any] = {}
    for channel in ("online", "program"):
        model = variants.get(f"channel:{channel}")
        if model is not None:
            separate[channel] = _evaluate(model, [e for e in data.test if e.channel == channel], spec, cfg)
    if separate:
        result["f2_per_channel"] = separate
    return result


def _all_groups_check(examples: list[Example], spec: ModelSpec, cfg: TrainingConfig) -> dict[str, Any]:
    """Предельная строгость: обучение изолировано от групп всех заявок теста. Если позитивов не остаётся —
    это ограничение объёма данных, а не повод ослаблять проверку."""
    data = split(examples, spec, cfg, all_test_groups=True)
    fitted = fit(data, spec, cfg, feature_names(spec))
    positives = int(_xy(data.train, feature_names(spec), spec, cfg)[1].sum())
    result: dict[str, Any] = {"train": len(data.train), "positives_train": positives, **data.isolation}
    if fitted is None:
        return result | {"status": "insufficient_labels"}
    return result | {"status": "trained", "test": _evaluate(fitted, data.test, spec, cfg)}


def to_version(
    spec: ModelSpec, fitted: Fitted, cfg: TrainingConfig, cutoff: datetime, summary: dict[str, Any], now: datetime
) -> ModelVersion:
    return ModelVersion(
        id=uuid4(),
        name=spec.name,
        typology=spec.typology,
        points=list(spec.points),
        feature_set_version=FEATURE_SET_VERSION,
        feature_names=fitted.names,
        artifact=fitted.booster.model_to_string(),
        calibration=fitted.calibration,
        training={"config": cfg.version, "params": cfg.lightgbm, "cutoff": cutoff.isoformat(), **summary["data"]},
        metrics={"test": summary["test"], "by_channel": summary["by_channel"]},
        created_at=now,
    )


def train_spec(
    examples: list[Example], spec: ModelSpec, cfg: TrainingConfig, cutoff: datetime, now: datetime, timezone: str
) -> tuple[ModelVersion | None, dict[str, Any]]:
    data = split(examples, spec, cfg)
    fitted = fit(data, spec, cfg, feature_names(spec))
    if fitted is None:
        positives = int(_xy(data.train, feature_names(spec), spec, cfg)[1].sum())
        return None, {
            "model": spec.name,
            "skipped": "insufficient_labels",
            "train": len(data.train),
            "positives_train": positives,
            **data.isolation,
        }
    variants: dict[str, Fitted | None] = {
        "per_application": fit(data, spec, cfg, feature_names(spec, frozenset({"zone2"})))
    }
    if len(spec.points) > 1:
        for channel in ("online", "program"):
            only = Split(
                [e for e in data.train if e.channel == channel],
                [e for e in data.calibration if e.channel == channel],
                [e for e in data.test if e.channel == channel],
                [],
                data.isolation,
            )
            variants[f"channel:{channel}"] = fit(only, spec, cfg, feature_names(spec))
    summary = report(spec, data, fitted, variants, cfg, timezone)
    summary["strict_all_groups"] = _all_groups_check(examples, spec, cfg)
    version = to_version(spec, fitted, cfg, cutoff, summary, now)
    summary["model_version_id"] = str(version.id)
    return version, summary
