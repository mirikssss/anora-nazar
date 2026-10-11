"""Чистая логика обзора: индекс стабильности популяции (PSI) признака между эталонным и последним окном."""

import math

from pydantic import BaseModel, ConfigDict, Field


class RiskConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    days: int = Field(gt=0)
    drift_recent_days: int = Field(gt=0)
    drift_reference_days: int = Field(gt=0)
    drift_bins: int = Field(gt=1)
    psi_floor: float = Field(gt=0)
    drift_features: list[str]


def psi(reference: list[float], recent: list[float], bins: int, floor: float) -> float | None:
    """PSI по квантилям эталона; доля в пустой корзине не ниже floor, чтобы логарифм был определён."""
    if len(reference) < bins or not recent:
        return None
    ordered = sorted(reference)
    edges = [ordered[int(len(ordered) * i / bins)] for i in range(1, bins)]

    def shares(values: list[float]) -> list[float]:
        counts = [0] * bins
        for v in values:
            counts[sum(1 for e in edges if v > e)] += 1
        return [max(c / len(values), floor) for c in counts]

    expected, actual = shares(reference), shares(recent)
    return round(sum((a - e) * math.log(a / e) for a, e in zip(actual, expected, strict=True)), 4)
