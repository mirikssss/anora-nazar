"""Чистая логика модуля: вектор признаков из агрегатов. Набор признаков версионируется целиком."""

from pydantic import BaseModel, ConfigDict

from node.modules.features.catalog.zone2 import ZONE2
from node.modules.index.domain import GroupView

FEATURE_SET_VERSION = "fs-1"
PASSPORTS = {p.name: p for p in ZONE2}


class FeatureVector(BaseModel):
    model_config = ConfigDict(frozen=True)

    set_version: str
    values: dict[str, float | int | bool]


def from_group(view: GroupView) -> FeatureVector:
    values: dict[str, float | int | bool] = {
        "independent_rare_links": view.independent_rare_links,
        "rare_links_weight": round(sum(link.weight for link in view.rare_links), 4),
        "group_applications": view.group_applications,
        "group_subjects": view.group_subjects,
        "group_recent_applications": view.recent_applications,
        "group_background_per_window": view.background_per_window,
        "group_burst": view.burst,
        "group_shared_roles": len(view.shared_roles),
    }
    unknown = values.keys() - PASSPORTS.keys()
    if unknown:
        raise AssertionError(f"Признаки без паспорта: {sorted(unknown)}")
    return FeatureVector(set_version=FEATURE_SET_VERSION, values=values)
