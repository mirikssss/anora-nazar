"""Каталог признаков по зонам (Блок 3) и параметры набора из YAML с версией."""

from node.modules.features.catalog.zone1 import ZONE1
from node.modules.features.catalog.zone2 import ZONE2
from node.modules.features.catalog.zone3 import CONTEXT, ZONE3
from node.modules.features.passport import FeaturePassport

PASSPORTS: dict[str, FeaturePassport] = {p.name: p for p in (*CONTEXT, *ZONE1, *ZONE2, *ZONE3)}
