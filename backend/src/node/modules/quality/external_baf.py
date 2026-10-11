"""Внешняя проверка подхода на BAF (Feedzai, NeurIPS 2022): та же LightGBM и те же метрики на открытом наборе
о мошенничестве при открытии счёта. Данных BAF в репозитории нет (Блок 3, «Лицензии»): файл скачивает сам
проверяющий, например `kaggle datasets download -d sgpjesus/bank-account-fraud-dataset-neurips-2022`.

Запуск: python -m node.modules.quality.external_baf <путь к Base.csv> [--config <scoring.yaml>]
Разбиение — по месяцам, как в статье BAF: месяцы 0–5 — обучение, 6–7 — тест; recall при 5 % FPR сравним с ней.
"""

import argparse
import csv
import json
import math
from pathlib import Path

import lightgbm as lgb
import numpy as np

from node.modules.quality.domain import metrics
from node.modules.scoring.training.config import load_training_config
from node.settings import PACKAGE_DIR

TARGET, MONTH = "fraud_bool", "month"
TRAIN_MONTHS = range(6)


def _load(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    names = [c for c in rows[0] if c not in (TARGET, MONTH)]
    categorical = [c for c in names if not _numeric(rows[0][c])]
    codes = {c: {v: i for i, v in enumerate(sorted({r[c] for r in rows}))} for c in categorical}
    x = np.array(
        [[codes[c][r[c]] if c in codes else float(r[c] or math.nan) for c in names] for r in rows], dtype=float
    )
    y = np.array([int(r[TARGET]) for r in rows])
    months = np.array([int(r[MONTH]) for r in rows])
    return x, y, months, names, categorical


def _numeric(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m node.modules.quality.external_baf")
    parser.add_argument("csv", type=Path)
    parser.add_argument("--config", type=Path, default=PACKAGE_DIR / "config" / "scoring.yaml")
    args = parser.parse_args()
    cfg = load_training_config(args.config)
    x, y, months, names, categorical = _load(args.csv)
    train = np.isin(months, list(TRAIN_MONTHS))
    data = lgb.Dataset(x[train], label=y[train], feature_name=names, categorical_feature=categorical)
    booster = lgb.train(dict(cfg.lightgbm), data)
    scores = np.asarray(booster.predict(x[~train]))
    result = metrics(y[~train], scores, review_share=cfg.review_share, fpr=cfg.fpr, probabilities=None)
    print(json.dumps({"dataset": args.csv.name, "config": cfg.version, "test_months": [6, 7], **result}))


if __name__ == "__main__":
    main()
