"""Метрики качества (Блок 3, «Метрики»): PR-AUC, recall при доле ручной проверки и при заданной доле ложных
тревог, мера Брайера, predictive equality, худшие дни по нагрузке. Чистые функции над массивами.
"""

from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from typing import Any

import numpy as np
from sklearn.metrics import average_precision_score


def _cut(scores: np.ndarray, share: float) -> float:
    """Порог, строго выше которого не больше доли share значений: при равных баллах — с запасом."""
    if scores.size == 0:
        return float("inf")
    ordered = np.sort(scores)[::-1]
    k = int(share * scores.size)
    return float(ordered[k]) if k < scores.size else float("-inf")


def threshold_at_share(scores: np.ndarray, share: float) -> float:
    """Выше порога — доля share заявок: столько банк может разобрать вручную."""
    return _cut(scores, share)


def threshold_at_fpr(y: np.ndarray, scores: np.ndarray, fpr: float) -> float:
    return _cut(scores[y == 0], fpr)


def recall_above(y: np.ndarray, scores: np.ndarray, threshold: float) -> float | None:
    positives = int(y.sum())
    if positives == 0:
        return None
    return round(float(((scores > threshold) & (y == 1)).sum()) / positives, 4)


def review_budget(y: np.ndarray, ranking: np.ndarray, share: float) -> dict[str, Any]:
    """Что даёт ручная проверка доли share заявок: сколько проверок, какая доля фрода поймана, сколько впустую."""
    flagged = ranking > threshold_at_share(ranking, share)
    reviewed = int(flagged.sum())
    caught = int((flagged & (y == 1)).sum())
    precision = round(caught / reviewed, 4) if reviewed else None
    return {
        "reviewed": reviewed,
        "recall": recall_above(y, ranking, threshold_at_share(ranking, share)),
        "precision": precision,
        "false_review_share": None if precision is None else round(1 - precision, 4),
    }


def pr_auc_interval(y: np.ndarray, ranking: np.ndarray, resamples: int, seed: int) -> list[float] | None:
    """95 % доверительный интервал PR-AUC бутстрепом по заявкам теста: при десятке позитивов он широкий."""
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(resamples):
        index = rng.integers(0, y.size, y.size)
        if 0 < y[index].sum() < y.size:
            values.append(average_precision_score(y[index], ranking[index]))
    if not values:
        return None
    low, high = np.quantile(values, [0.025, 0.975])
    return [round(float(low), 4), round(float(high), 4)]


def metrics(
    y: np.ndarray,
    ranking: np.ndarray,
    *,
    review_shares: list[float],
    fpr: float,
    probabilities: np.ndarray | None,
    bootstrap: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """Ранжирующие метрики — по сырому баллу: изотоническая калибровка ступенчатая и даёт много равных значений.
    Мера Брайера — по калиброванной вероятности. Случайный ранжир даёт PR-AUC, равный доле позитивов."""
    positives = int(y.sum())
    rate = round(positives / y.size, 5) if y.size else None
    result: dict[str, Any] = {
        "applications": int(y.size),
        "positives": positives,
        "positive_rate": rate,
        "random_pr_auc": rate,
    }
    if positives in (0, y.size):
        return result | {"pr_auc": None, "pr_auc_ci95": None, "review": {}, "recall_at_fpr": None, "brier": None}
    return result | {
        "pr_auc": round(float(average_precision_score(y, ranking)), 4),
        "pr_auc_ci95": None if bootstrap is None else pr_auc_interval(y, ranking, *bootstrap),
        "review": {f"{share:.0%}": review_budget(y, ranking, share) for share in review_shares},
        "recall_at_fpr": recall_above(y, ranking, threshold_at_fpr(y, ranking, fpr)),
        "brier": None if probabilities is None else round(float(np.mean((probabilities - y) ** 2)), 5),
    }


def predictive_equality(y: np.ndarray, scores: np.ndarray, groups: Sequence[str], threshold: float) -> dict[str, Any]:
    """Доля ложных тревог по группам при одном пороге и наибольший разрыв между ними."""
    by_group: dict[str, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        if y[index] == 0:
            by_group[group].append(index)
    rates = {group: round(float((scores[idx] > threshold).mean()), 4) for group, idx in sorted(by_group.items()) if idx}
    gap = round(max(rates.values()) - min(rates.values()), 4) if len(rates) > 1 else 0.0
    return {"false_positive_rate": rates, "max_gap": gap}


def worst_days(days: Sequence[date], flagged: np.ndarray) -> dict[str, Any]:
    """Нагрузка проверки по дням тестового периода: худший день и 95-й перцентиль (ревью C)."""
    per_day: dict[date, list[int]] = defaultdict(lambda: [0, 0])
    for day, flag in zip(days, flagged, strict=True):
        per_day[day][0] += 1
        per_day[day][1] += int(flag)
    if not per_day:
        return {"days": 0}
    loads = np.array([flags for _total, flags in per_day.values()])
    worst_day, (total, flags) = max(per_day.items(), key=lambda item: item[1][1])
    return {
        "days": len(per_day),
        "mean_flagged_per_day": round(float(loads.mean()), 2),
        "p95_flagged_per_day": round(float(np.quantile(loads, 0.95)), 2),
        "worst_day": worst_day.isoformat(),
        "worst_day_flagged": flags,
        "worst_day_applications": total,
    }
