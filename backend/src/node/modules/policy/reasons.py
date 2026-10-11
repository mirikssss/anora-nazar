"""Код причины: {code, typology, source: rule|model|graph|network, evidence, norm}. Тексты — в модуле texts."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

Level = Literal["green", "yellow", "red"]
Typology = Literal["F1", "F2", "F3"]
ReasonSource = Literal["rule", "model", "graph", "network"]

LEVEL_ORDER: dict[Level, int] = {"green": 0, "yellow": 1, "red": 2}


def max_level(levels: list[Level]) -> Level:
    return max(levels, key=LEVEL_ORDER.__getitem__, default="green")


class CatalogEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    source: ReasonSource
    typology: Typology | None = None
    norm: str | None = None


class Reason(BaseModel):
    """Причина в записи решения. level — какой уровень она даёт; None — только сведение."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    typology: Typology | None
    source: ReasonSource
    evidence: list[dict[str, Any]]
    norm: str | None
    level: Level | None
