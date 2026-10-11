"""Параметры обучения из config/scoring.yaml."""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from node.modules.features.passport import FeaturePoint, Group
from node.modules.policy.reasons import Typology
from shared.config import load_yaml

Family = Literal["lightgbm", "logistic"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EvaluationConfig(_Frozen):
    folds: int = Field(gt=0)
    test_span: float = Field(gt=0, lt=1)
    validation_share: float = Field(gt=0, lt=1)


class BoostingConfig(_Frozen):
    max_rounds: int = Field(gt=0)
    early_stopping_rounds: int = Field(gt=0)


class LogisticConfig(_Frozen):
    c: float = Field(gt=0)
    max_iter: int = Field(gt=0)


class ModelSpec(_Frozen):
    name: str
    typology: Typology
    points: list[FeaturePoint]
    groups: list[Group]
    calibrate_by_channel: bool


class TrainingConfig(_Frozen):
    version: str
    feature_set: str
    evaluation: EvaluationConfig
    weak_negative_weight: float = Field(gt=0, le=1)
    min_positives: int = Field(gt=0)
    min_calibration_positives: int = Field(gt=0)
    review_share: float = Field(gt=0, lt=1)
    review_shares: list[float] = Field(min_length=1)
    fpr: float = Field(gt=0, lt=1)
    bootstrap_resamples: int = Field(gt=0)
    point_in_time_sample: int = Field(ge=0)
    age_bands: list[int]
    candidates: list[Family] = Field(min_length=1)
    lightgbm: dict[str, Any]
    boosting: BoostingConfig
    logistic: LogisticConfig
    monotone: dict[str, Literal[-1, 1]]
    models: list[ModelSpec]
    f2_mode: Literal["shared", "per_channel"]

    @property
    def seed(self) -> int:
        return int(self.lightgbm["seed"])


def load_training_config(path: Path) -> TrainingConfig:
    return TrainingConfig.model_validate(load_yaml(path))
