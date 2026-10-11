"""Параметры обучения из config/scoring.yaml."""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from node.modules.features.passport import FeaturePoint, Group
from node.modules.policy.reasons import Typology
from shared.config import load_yaml


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SplitConfig(_Frozen):
    train: float = Field(gt=0)
    calibration: float = Field(gt=0)
    test: float = Field(gt=0)


class ModelSpec(_Frozen):
    name: str
    typology: Typology
    points: list[FeaturePoint]
    groups: list[Group]
    calibrate_by_channel: bool


class TrainingConfig(_Frozen):
    version: str
    feature_set: str
    split: SplitConfig
    weak_negative_weight: float = Field(gt=0, le=1)
    min_positives: int = Field(gt=0)
    min_calibration_positives: int = Field(gt=0)
    review_share: float = Field(gt=0, lt=1)
    fpr: float = Field(gt=0, lt=1)
    age_bands: list[int]
    lightgbm: dict[str, Any]
    models: list[ModelSpec]
    f2_mode: Literal["shared", "per_channel"]


def load_training_config(path: Path) -> TrainingConfig:
    return TrainingConfig.model_validate(load_yaml(path))
