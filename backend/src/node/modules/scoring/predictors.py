"""Предсказатели моделей реестра с общим интерфейсом: сырой балл и вклад признаков в балл.

LightGBM — вклад через SHAP-значения бустера. Логистическая регрессия — коэффициент × стандартизованное значение;
пропуск заменяется медианой обучения и даёт отдельный признак-индикатор, его вклад прибавляется к признаку.
"""

import json
from dataclasses import dataclass
from typing import Literal, Protocol

import lightgbm as lgb
import numpy as np

Kind = Literal["lightgbm", "logistic"]


class Predictor(Protocol):
    def raw(self, rows: np.ndarray) -> np.ndarray: ...

    def contributions(self, row: np.ndarray) -> list[float]: ...


@dataclass(frozen=True)
class BoosterPredictor:
    booster: lgb.Booster

    def raw(self, rows: np.ndarray) -> np.ndarray:
        return np.asarray(self.booster.predict(rows))

    def contributions(self, row: np.ndarray) -> list[float]:
        return [float(c) for c in np.asarray(self.booster.predict(row[None, :], pred_contrib=True))[0][:-1]]

    def to_artifact(self) -> str:
        return str(self.booster.model_to_string())


@dataclass(frozen=True)
class LogisticModel:
    median: tuple[float, ...]
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    indicators: tuple[int, ...]
    coef: tuple[float, ...]
    intercept: float

    def design(self, rows: np.ndarray) -> np.ndarray:
        x = np.array(rows, dtype=float)
        missing = np.isnan(x)
        x[missing] = np.take(np.array(self.median), np.nonzero(missing)[1])
        z = (x - np.array(self.mean)) / np.array(self.scale)
        return np.hstack([z, missing[:, list(self.indicators)].astype(float)])

    def raw(self, rows: np.ndarray) -> np.ndarray:
        logits = self.design(rows) @ np.array(self.coef) + self.intercept
        return np.asarray(1 / (1 + np.exp(-logits)))

    def contributions(self, row: np.ndarray) -> list[float]:
        parts = self.design(row[None, :])[0] * np.array(self.coef)
        width = len(self.mean)
        result = parts[:width].copy()
        for offset, feature in enumerate(self.indicators):
            result[feature] += parts[width + offset]
        return [float(v) for v in result]

    def to_artifact(self) -> str:
        return json.dumps(
            {
                "median": self.median,
                "mean": self.mean,
                "scale": self.scale,
                "indicators": self.indicators,
                "coef": self.coef,
                "intercept": self.intercept,
            }
        )

    @classmethod
    def from_artifact(cls, text: str) -> "LogisticModel":
        data = json.loads(text)
        return cls(
            median=tuple(data["median"]),
            mean=tuple(data["mean"]),
            scale=tuple(data["scale"]),
            indicators=tuple(data["indicators"]),
            coef=tuple(data["coef"]),
            intercept=float(data["intercept"]),
        )


def load(kind: str, artifact: str) -> Predictor:
    if kind == "logistic":
        return LogisticModel.from_artifact(artifact)
    return BoosterPredictor(lgb.Booster(model_str=artifact))
