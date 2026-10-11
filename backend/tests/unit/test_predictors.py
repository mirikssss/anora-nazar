"""Логистическая модель реестра: пропуск — медиана плюс индикатор, вклад индикатора — к своему признаку."""

import math

import numpy as np

from node.modules.scoring.predictors import LogisticModel

MODEL = LogisticModel(
    median=(1.0, 0.0), mean=(1.0, 0.5), scale=(2.0, 0.5), indicators=(1,), coef=(0.8, -0.4, 1.2), intercept=-3.0
)


def test_missing_value_uses_median_and_indicator() -> None:
    row = np.array([3.0, math.nan])
    design = MODEL.design(row[None, :])[0]
    assert design.tolist() == [1.0, -1.0, 1.0]
    logit = 0.8 * 1.0 + -0.4 * -1.0 + 1.2 * 1.0 - 3.0
    assert math.isclose(MODEL.raw(row[None, :])[0], 1 / (1 + math.exp(-logit)))
    assert MODEL.contributions(row) == [0.8, 0.4 + 1.2], "вклад индикатора пропуска прибавлен к своему признаку"


def test_artifact_round_trip() -> None:
    assert LogisticModel.from_artifact(MODEL.to_artifact()) == MODEL
