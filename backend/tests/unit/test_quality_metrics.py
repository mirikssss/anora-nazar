"""Метрики качества на маленьких массивах с известным ответом."""

from datetime import date

import numpy as np

from node.modules.quality.domain import metrics, predictive_equality, threshold_at_fpr, worst_days


def test_recall_at_review_share_and_fpr() -> None:
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    scores = np.array([0.9, 0.2, 0.8, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1])
    result = metrics(y, scores, review_shares=[0.2], fpr=0.2, probabilities=scores, bootstrap=(200, 1))
    review = result["review"]["20%"]
    assert review["recall"] == 0.5, "верхние 20 % — 0.9 и 0.8, пойман один из двух"
    assert review["precision"] == 0.5 and review["false_review_share"] == 0.5
    assert result["random_pr_auc"] == 0.2
    low, high = result["pr_auc_ci95"]
    assert 0 <= low <= result["pr_auc"] <= high <= 1
    assert result["recall_at_fpr"] == 1.0, "выше 0.1 — один негатив из восьми (12,5 % ≤ 20 %) и оба позитива"
    assert 0 < result["pr_auc"] <= 1
    assert result["brier"] is not None
    assert threshold_at_fpr(y, scores, 0.2) <= 0.8


def test_metrics_without_positives_are_empty_not_zero() -> None:
    result = metrics(np.zeros(5), np.ones(5) * 0.1, review_shares=[0.2], fpr=0.05, probabilities=None)
    assert result["pr_auc"] is None and result["review"] == {}


def test_predictive_equality_gap_and_worst_day() -> None:
    y = np.array([0, 0, 0, 0])
    scores = np.array([0.9, 0.1, 0.9, 0.9])
    equality = predictive_equality(y, scores, ["a", "a", "b", "b"], 0.5)
    assert equality["false_positive_rate"] == {"a": 0.5, "b": 1.0}
    assert equality["max_gap"] == 0.5
    days = [date(2026, 9, 1), date(2026, 9, 1), date(2026, 9, 2)]
    load = worst_days(days, np.array([True, True, False]))
    assert load["worst_day"] == "2026-09-01" and load["worst_day_flagged"] == 2
