"""Обучение моделей «типология × точки».

Качество меряется скользящей проверкой по времени: каждое окно последних меток предсказывает модель, обученная
только на более раннем, с изоляцией групп мошенников окна и их поставщиков. Семейство (LightGBM с монотонностью
или логистическая регрессия) выбирается по PR-AUC этой проверки; выпускаемая модель обучается на всех метках,
калибровка — по предсказаниям вне выборки. Отчёт сравнивает модель с правилами и графом без ML, поштучную модель
с моделью + граф, общую F2 с раздельными по каналам (ревью D) и показывает нагрузку худших дней (ревью C).
"""

import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import lightgbm as lgb
import numpy as np
from sklearn.linear_model import LogisticRegression

from node.modules.features.catalog import PASSPORTS
from node.modules.features.domain import FEATURE_SET_VERSION
from node.modules.quality.domain import metrics, predictive_equality, threshold_at_share, worst_days
from node.modules.scoring.domain import calibrate, feature_row
from node.modules.scoring.models import ModelVersion
from node.modules.scoring.predictors import BoosterPredictor, LogisticModel
from node.modules.scoring.training.calibrate import calibration
from node.modules.scoring.training.config import NETWORK_GROUP, Family, ModelSpec, TrainingConfig
from node.modules.scoring.training.dataset import Example, age_band, gender

PER_APPLICATION = frozenset({"zone2"})  # поштучная модель — без признаков графа


@dataclass(frozen=True)
class Fold:
    train: list[Example]
    validation: list[Example]
    test: list[Example]
    unlabeled: list[Example]
    isolation: dict[str, int]


@dataclass(frozen=True)
class Fitted:
    family: Family
    predictor: BoosterPredictor | LogisticModel
    names: list[str]
    rounds: int | None


@dataclass
class OutOfFold:
    """Предсказания окон проверки: каждая заявка оценена моделью, не видевшей её окна."""

    examples: list[Example] = field(default_factory=list)
    raw: list[float] = field(default_factory=list)
    probabilities: list[float] = field(default_factory=list)
    rounds: list[int] = field(default_factory=list)

    def add(self, fitted: Fitted, fold: Fold, cfg: TrainingConfig, spec: ModelSpec) -> None:
        test_raw = raw_scores(fitted, fold.test)
        curve = _validation_curve(fitted, fold.validation, cfg, spec)
        self.examples += fold.test
        self.raw += [float(v) for v in test_raw]
        self.probabilities += [
            float(v) if curve is None else calibrate(float(v), curve, e.channel)
            for v, e in zip(test_raw, fold.test, strict=True)
        ]
        if fitted.rounds is not None:
            self.rounds.append(fitted.rounds)


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


def _positive(example: Example, spec: ModelSpec, cfg: TrainingConfig) -> bool:
    return target(example, spec.typology, cfg.weak_negative_weight) == (1, 1.0)


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


def _edges(labeled: list[Example], cfg: TrainingConfig) -> dict[str, list[datetime]]:
    """Границы окон проверки внутри канала: метки онлайн-займов и программ созревают по-разному."""
    span, count = cfg.evaluation.test_span, cfg.evaluation.folds
    edges: dict[str, list[datetime]] = {}
    for channel in {e.channel for e in labeled}:
        own = [e.as_of for e in labeled if e.channel == channel]
        positions = [int(len(own) * (1 - span + span * i / count)) for i in range(count)]
        edges[channel] = [own[min(p, len(own) - 1)] for p in positions] + [datetime.max.replace(tzinfo=own[0].tzinfo)]
    return edges


def _tail_split(examples: list[Example], share: float) -> tuple[list[Example], list[Example]]:
    """Хвост по времени внутри канала — для ранней остановки и калибровки окна."""
    head, tail = [], []
    for channel in {e.channel for e in examples}:
        own = [e for e in examples if e.channel == channel]
        cut = int(len(own) * (1 - share))
        head += own[:cut]
        tail += own[cut:]
    return sorted(head, key=lambda e: e.as_of), sorted(tail, key=lambda e: e.as_of)


def folds(
    examples: list[Example], spec: ModelSpec, cfg: TrainingConfig, *, all_test_groups: bool = False
) -> list[Fold]:
    """Окна скользящей проверки. Строго: в обучение окна не попадает ни одна заявка из одной группы с мошенниками
    окна (человек, телефон, устройство, адрес, дело) и ни один поставщик их схем. all_test_groups=True —
    изоляция от групп всех заявок окна, включая честные (проверка на пределе строгости)."""
    scoped = [e for e in examples if e.point in spec.points]
    labeled = [e for e in scoped if target(e, spec.typology, cfg.weak_negative_weight) is not None]
    if not labeled:
        return []
    labeled_ids = {e.application_id for e in labeled}
    group_of = groups(scoped)
    edges = _edges(labeled, cfg)
    result = []
    for k in range(cfg.evaluation.folds):

        def inside(e: Example, k: int = k) -> bool:
            return e.channel in edges and edges[e.channel][k] <= e.as_of < edges[e.channel][k + 1]

        test = [e for e in labeled if inside(e)]
        frauds = [e for e in test if _positive(e, spec, cfg)]
        isolated_groups = {group_of[e.application_id] for e in (test if all_test_groups else frauds)}
        suppliers = {e.supplier for e in frauds if e.supplier}
        before = [e for e in labeled if e.as_of < edges[e.channel][k]]
        kept = [e for e in before if group_of[e.application_id] not in isolated_groups and e.supplier not in suppliers]
        train, validation = _tail_split(kept, cfg.evaluation.validation_share)
        result.append(
            Fold(
                train=train,
                validation=validation,
                test=test,
                unlabeled=[e for e in scoped if e.application_id not in labeled_ids and inside(e)],
                isolation={"excluded_from_training": len(before) - len(kept), "held_out_suppliers": len(suppliers)},
            )
        )
    return result


def _xy(examples: list[Example], names: list[str], spec: ModelSpec, cfg: TrainingConfig) -> tuple[Any, Any, Any]:
    targets = [target(e, spec.typology, cfg.weak_negative_weight) for e in examples]
    x = np.array([feature_row(names, e.values) for e in examples], dtype=float).reshape(len(examples), len(names))
    y = np.array([t[0] if t else 0 for t in targets], dtype=float)
    w = np.array([t[1] if t else 0.0 for t in targets], dtype=float)
    return x, y, w


def _boost(
    x: np.ndarray, y: np.ndarray, w: np.ndarray, names: list[str], cfg: TrainingConfig, rounds: int, valid: Any = None
) -> lgb.Booster:
    params = dict(cfg.lightgbm) | {"monotone_constraints": [cfg.monotone.get(n, 0) for n in names]}
    data = lgb.Dataset(x, label=y, weight=w, feature_name=names, free_raw_data=True)
    if valid is None:
        return lgb.train(params, data, num_boost_round=rounds)
    vx, vy, vw = valid
    check = lgb.Dataset(vx, label=vy, weight=vw, reference=data)
    stop = lgb.early_stopping(cfg.boosting.early_stopping_rounds, verbose=False)
    return lgb.train(params, data, num_boost_round=rounds, valid_sets=[check], callbacks=[stop])


def _logistic(x: np.ndarray, y: np.ndarray, w: np.ndarray, cfg: TrainingConfig) -> LogisticModel:
    missing = np.isnan(x)
    median = [float(np.median(col[~gap])) if (~gap).any() else 0.0 for col, gap in zip(x.T, missing.T, strict=True)]
    filled = np.where(missing, np.array(median), x)
    mean, scale = filled.mean(axis=0), filled.std(axis=0)
    scale[scale == 0] = 1.0
    indicators = tuple(j for j in range(x.shape[1]) if missing[:, j].any())
    shell = LogisticModel(tuple(median), tuple(mean.tolist()), tuple(scale.tolist()), indicators, (), 0.0)
    model = LogisticRegression(C=cfg.logistic.c, max_iter=cfg.logistic.max_iter)
    model.fit(shell.design(x), y, sample_weight=w)
    return LogisticModel(
        shell.median, shell.mean, shell.scale, indicators, tuple(model.coef_[0].tolist()), float(model.intercept_[0])
    )


def fit(
    family: Family,
    train: list[Example],
    validation: list[Example],
    spec: ModelSpec,
    cfg: TrainingConfig,
    names: list[str],
    rounds: int | None = None,
) -> Fitted | None:
    """rounds=None — ранняя остановка по хвосту обучения; число — финальная модель на всех метках."""
    x, y, w = _xy(train, names, spec, cfg)
    if int(y.sum()) < cfg.min_positives:
        return None
    if family == "logistic":
        return Fitted(family, _logistic(x, y, w, cfg), names, None)
    valid = _xy(validation, names, spec, cfg) if validation else None
    if rounds is None and valid is not None and valid[1].sum() > 0:
        booster = _boost(x, y, w, names, cfg, cfg.boosting.max_rounds, valid)
        return Fitted(family, BoosterPredictor(booster), names, booster.best_iteration or cfg.boosting.max_rounds)
    chosen = rounds or cfg.boosting.max_rounds
    return Fitted(family, BoosterPredictor(_boost(x, y, w, names, cfg, chosen)), names, chosen)


def raw_scores(fitted: Fitted, examples: list[Example]) -> np.ndarray:
    if not examples:
        return np.array([])
    rows = np.array([feature_row(fitted.names, e.values) for e in examples], dtype=float)
    return fitted.predictor.raw(rows)


def _curve(raw: np.ndarray, examples: list[Example], spec: ModelSpec, cfg: TrainingConfig, source: str) -> Any:
    _, y, _ = _xy(examples, [], spec, cfg)
    channels = np.array([e.channel for e in examples])
    return calibration(
        raw,
        y,
        channels,
        by_channel=spec.calibrate_by_channel,
        min_positives=cfg.min_calibration_positives,
        source=source,
    )


def _validation_curve(fitted: Fitted, validation: list[Example], cfg: TrainingConfig, spec: ModelSpec) -> Any:
    """Калибровка окна — по хвосту его обучения; без позитивов в хвосте калибровать нечем."""
    _, y, _ = _xy(validation, [], spec, cfg)
    if not validation or y.sum() == 0:
        return None
    return _curve(raw_scores(fitted, validation), validation, spec, cfg, "validation")


def _metrics(
    y: np.ndarray, ranking: np.ndarray, cfg: TrainingConfig, probabilities: np.ndarray | None
) -> dict[str, Any]:
    return metrics(
        y,
        ranking,
        review_shares=cfg.review_shares,
        fpr=cfg.fpr,
        probabilities=probabilities,
        bootstrap=(cfg.bootstrap_resamples, cfg.seed),
    )


def _oof_metrics(oof: OutOfFold, spec: ModelSpec, cfg: TrainingConfig) -> dict[str, Any]:
    _, y, _ = _xy(oof.examples, [], spec, cfg)
    return _metrics(y, np.array(oof.raw), cfg, np.array(oof.probabilities))


def _by_channel(oof: OutOfFold, spec: ModelSpec, cfg: TrainingConfig) -> dict[str, Any]:
    result = {}
    for channel in ("online", "program"):
        index = [i for i, e in enumerate(oof.examples) if e.channel == channel]
        if index:
            part = OutOfFold(
                [oof.examples[i] for i in index], [oof.raw[i] for i in index], [oof.probabilities[i] for i in index]
            )
            result[channel] = _oof_metrics(part, spec, cfg)
    return result


def _cross_validate(
    fold_list: list[Fold], family: Family, spec: ModelSpec, cfg: TrainingConfig, names: list[str]
) -> tuple[OutOfFold, Fitted | None]:
    """Предсказания всех окон и модель последнего окна (по ней — нагрузка худших дней)."""
    oof, last = OutOfFold(), None
    for fold in fold_list:
        fitted = fit(family, fold.train, fold.validation, spec, cfg, names)
        if fitted is not None:
            oof.add(fitted, fold, cfg, spec)
            last = fitted
    return oof, last


def _per_channel(fold_list: list[Fold], family: Family, spec: ModelSpec, cfg: TrainingConfig) -> dict[str, Any]:
    """Раздельные F2: модель на каждый канал, те же окна (ревью D)."""
    result = {}
    for channel in ("online", "program"):
        only = [
            Fold(
                [e for e in f.train if e.channel == channel],
                [e for e in f.validation if e.channel == channel],
                [e for e in f.test if e.channel == channel],
                [],
                f.isolation,
            )
            for f in fold_list
        ]
        oof, _ = _cross_validate(only, family, spec, cfg, feature_names(spec))
        if oof.examples:
            result[channel] = _oof_metrics(oof, spec, cfg)
    return result


def _local_day(moment: datetime, timezone: str) -> Any:
    return moment.astimezone(ZoneInfo(timezone)).date()


def _all_groups_check(examples: list[Example], family: Family, spec: ModelSpec, cfg: TrainingConfig) -> dict[str, Any]:
    """Предельная строгость: обучение изолировано от групп всех заявок окна. Если позитивов не остаётся —
    это ограничение объёма данных, а не повод ослаблять проверку."""
    fold_list = folds(examples, spec, cfg, all_test_groups=True)
    oof, _ = _cross_validate(fold_list, family, spec, cfg, feature_names(spec))
    positives = [int(_xy(f.train, [], spec, cfg)[1].sum()) for f in fold_list]
    result: dict[str, Any] = {"positives_train_by_fold": positives}
    if not oof.examples:
        return result | {"status": "insufficient_labels"}
    return result | {"status": "trained", "test": _oof_metrics(oof, spec, cfg)}


def _fold_summary(fold_list: list[Fold], spec: ModelSpec, cfg: TrainingConfig) -> list[dict[str, Any]]:
    return [
        {
            "train": len(f.train),
            "positives_train": int(_xy(f.train, [], spec, cfg)[1].sum()),
            "test": len(f.test),
            "positives_test": int(_xy(f.test, [], spec, cfg)[1].sum()),
            "test_from": f.test[0].as_of.isoformat() if f.test else None,
            **f.isolation,
        }
        for f in fold_list
    ]


def _report(
    spec: ModelSpec,
    family: Family,
    candidates: dict[str, OutOfFold],
    fold_list: list[Fold],
    last: Fitted | None,
    examples: list[Example],
    cfg: TrainingConfig,
    timezone: str,
) -> dict[str, Any]:
    oof = candidates[family]
    _, y, _ = _xy(oof.examples, [], spec, cfg)
    ranking = np.array(oof.raw)
    threshold = threshold_at_share(ranking, cfg.review_share)
    without_network = frozenset({NETWORK_GROUP})
    solo, _ = _cross_validate(fold_list, family, spec, cfg, feature_names(spec, PER_APPLICATION | without_network))
    local = (
        _cross_validate(fold_list, family, spec, cfg, feature_names(spec, without_network))[0]
        if spec.uses_network
        else oof
    )
    baseline = np.array([e.rules_score for e in oof.examples])
    on_day = max(e.as_of for e in oof.examples).date()
    tail = fold_list[-1].test + fold_list[-1].unlabeled
    tail_scores = raw_scores(last, tail) if last is not None else np.array([])
    result: dict[str, Any] = {
        "model": spec.name,
        "typology": spec.typology,
        "points": spec.points,
        "family": family,
        "folds": _fold_summary(fold_list, spec, cfg),
        "candidates": {name: _oof_metrics(c, spec, cfg) for name, c in candidates.items() if c.examples},
        "test": _oof_metrics(oof, spec, cfg),
        "by_channel": _by_channel(oof, spec, cfg),
        # Блок 3, главный эксперимент: поштучно → + граф → + сеть на тех же окнах и при той же доле проверки
        "ablation": {
            "rules_graph_baseline": _metrics(y, baseline, cfg, None),
            "per_application": _oof_metrics(solo, spec, cfg) if solo.examples else None,
            "with_graph": _oof_metrics(local, spec, cfg) if local.examples else None,
            "with_graph_and_network": (
                _oof_metrics(oof, spec, cfg) if spec.uses_network else {"status": "see_network_variant"}
            ),
        },
        "fairness": {
            "threshold": round(threshold, 6),
            "gender": predictive_equality(y, ranking, [gender(e.pinfl) for e in oof.examples], threshold),
            "age_band": predictive_equality(
                y, ranking, [age_band(e.pinfl, on_day, cfg.age_bands) for e in oof.examples], threshold
            ),
        },
        "load": worst_days([_local_day(e.as_of, timezone) for e in tail], tail_scores > threshold),
        "strict_all_groups": _all_groups_check(examples, family, spec, cfg),
    }
    if len(spec.points) > 1:
        result["f2_per_channel"] = _per_channel(fold_list, family, spec, cfg)
    return result


def _network_answered(examples: list[Example], spec: ModelSpec) -> bool:
    names = set(feature_names(spec)) - set(feature_names(spec, frozenset({NETWORK_GROUP})))
    return any(e.values.get(name) is not None for e in examples if e.point in spec.points for name in names)


def train_spec(
    examples: list[Example], spec: ModelSpec, cfg: TrainingConfig, cutoff: datetime, now: datetime, timezone: str
) -> tuple[ModelVersion | None, dict[str, Any]]:
    if spec.uses_network and not _network_answered(examples, spec):
        return None, {"model": spec.name, "skipped": "network_unavailable"}
    fold_list = folds(examples, spec, cfg)
    names = feature_names(spec)
    candidates: dict[str, OutOfFold] = {}
    lasts: dict[str, Fitted | None] = {}
    for family in cfg.candidates:
        candidates[family], lasts[family] = _cross_validate(fold_list, family, spec, cfg, names)
    scored = {f: _oof_metrics(c, spec, cfg).get("pr_auc") for f, c in candidates.items() if c.examples}
    labeled = [e for e in examples if e.point in spec.points and target(e, spec.typology, 1.0) is not None]
    positives = int(_xy(labeled, [], spec, cfg)[1].sum())
    if not scored or all(v is None for v in scored.values()):
        folds_info = _fold_summary(fold_list, spec, cfg)
        return None, {"model": spec.name, "skipped": "insufficient_labels", "positives": positives, "folds": folds_info}
    family = max((f for f in cfg.candidates if scored.get(f) is not None), key=lambda f: scored[f] or 0.0)
    oof = candidates[family]
    rounds = int(statistics.median(oof.rounds)) if oof.rounds else None
    final = fit(family, labeled, [], spec, cfg, names, rounds=rounds or cfg.boosting.max_rounds)
    summary = _report(spec, family, candidates, fold_list, lasts[family], examples, cfg, timezone)
    summary["final"] = {"train": len(labeled), "positives": positives, "rounds": rounds}
    if final is None:
        return None, summary | {"skipped": "insufficient_labels"}
    curve = _curve(np.array(oof.raw), oof.examples, spec, cfg, "out_of_fold")
    version = ModelVersion(
        id=uuid4(),
        name=spec.name,
        typology=spec.typology,
        points=list(spec.points),
        feature_set_version=FEATURE_SET_VERSION,
        kind=family,
        feature_names=names,
        artifact=final.predictor.to_artifact(),
        calibration=curve,
        training={
            "config": cfg.version,
            "family": family,
            "params": cfg.lightgbm if family == "lightgbm" else cfg.logistic.model_dump(),
            "rounds": rounds,
            "cutoff": cutoff.isoformat(),
            **summary["final"],
        },
        metrics={"test": summary["test"], "by_channel": summary["by_channel"]},
        created_at=now,
    )
    summary["model_version_id"] = str(version.id)
    return version, summary
