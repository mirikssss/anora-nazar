"""Чистая логика модуля: итог скоринга и проверка контракта признаков."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ModelScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_version_id: str
    typology: Literal["F1", "F2", "F3"]
    probability: float


class ScoringOutcome(BaseModel):
    """Итог скоринга. Без совместимой модели — режим «без модели» с причиной, а не выдуманный балл."""

    model_config = ConfigDict(frozen=True)

    status: Literal["no_model", "scored"]
    reason: Literal["registry_empty", "contract_mismatch"] | None
    checked_models: list[str]
    scores: list[ModelScore]


def contract_matches(model_points: list[str], model_feature_set: str, point: str, feature_set: str) -> bool:
    return point in model_points and model_feature_set == feature_set
