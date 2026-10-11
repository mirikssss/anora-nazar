"""Чистая логика скоринга: контракт признаков, строка модели, калибровка, вклад признаков → коды причин."""

import math
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from node.modules.features.catalog import PASSPORTS
from node.modules.features.domain import Value

Channel = Literal["online", "program"]


class Contribution(BaseModel):
    model_config = ConfigDict(frozen=True)

    feature: str
    value: Value
    contribution: float
    reason_code: str | None


class ModelScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_version_id: str
    name: str
    typology: Literal["F1", "F2", "F3"]
    probability: float
    contributions: list[Contribution]


class ScoringOutcome(BaseModel):
    """Итог скоринга. Без совместимой модели — режим «без модели» с причиной, а не выдуманный балл."""

    model_config = ConfigDict(frozen=True)

    status: Literal["no_model", "scored"]
    reason: Literal["registry_empty", "contract_mismatch", "partial"] | None
    checked_models: list[str]
    scores: list[ModelScore]
    missing_typologies: list[str] = []
    shadow: list[ModelScore] = []


def contract_matches(model_points: list[str], model_feature_set: str, point: str, feature_set: str) -> bool:
    return point in model_points and model_feature_set == feature_set


def requires_network(feature_names: list[str]) -> bool:
    """Модель с признаками сети запускается, только когда сеть ответила; иначе работает локальная."""
    return any(PASSPORTS[name].group == "network" for name in feature_names if name in PASSPORTS)


def as_number(value: Value) -> float:
    """Пропуск остаётся пропуском: LightGBM учитывает отсутствие данных явно (Блок 3)."""
    if value is None:
        return math.nan
    return float(value)


def feature_row(names: list[str], values: dict[str, Value]) -> list[float]:
    return [as_number(values.get(name)) for name in names]


def calibrate(raw: float, calibration: dict[str, Any], channel: Channel) -> float:
    """Изотоническая калибровка: по каналу, если для него есть своя кривая, иначе общая."""
    maps = calibration["maps"]
    curve = maps.get(channel) if calibration.get("by") == "channel" else None
    curve = curve or maps["all"]
    return round(float(np.interp(raw, curve["x"], curve["y"])), 6)


def top_contributions(
    names: list[str], values: dict[str, Value], contributions: list[float], limit: int
) -> list[Contribution]:
    """Признаки, сильнее всего поднявшие балл, — из них собираются причины для аналитика."""
    ranked = sorted((item for item in zip(names, contributions, strict=True) if item[1] > 0), key=lambda item: -item[1])
    return [
        Contribution(
            feature=name,
            value=values.get(name),
            contribution=round(value, 4),
            reason_code=PASSPORTS[name].reason_code,
        )
        for name, value in ranked[:limit]
    ]


def channel_of(values: dict[str, Value]) -> Channel:
    return "online" if values.get("channel_online") else "program"
