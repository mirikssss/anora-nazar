"""Проверка point-in-time: признаки прошлых решений пересчитываются из сегодняшней базы на их as_of.

В базе уже лежат все будущие факты, связи и метки. Если пересчёт совпадает с тем, что решение записало в момент
оценки, — функции признаков не заглядывают в будущее. Любое расхождение — утечка или недетерминизм.
"""

from dataclasses import dataclass
from random import Random
from typing import Any

from sqlalchemy.orm import Session

from node.modules.decisions import service as decisions
from node.modules.features import service as features
from node.modules.features.domain import FEATURE_SET_VERSION, Point
from node.modules.policy.domain import Policy
from node.modules.realms.domain import RealmContext
from shared.contracts.application import ApplicationSnapshot

EXAMPLES_LIMIT = 5  # сколько расхождений показать в отчёте


@dataclass(frozen=True)
class PointInTimeReport:
    checked: int
    mismatched: int
    by_feature: dict[str, int]
    examples: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "checked": self.checked,
            "mismatched": self.mismatched,
            "by_feature": self.by_feature,
            "examples": self.examples,
        }


def check(
    session: Session, realm: RealmContext, policy: Policy, index_key: bytes, sample: int, seed: int
) -> PointInTimeReport:
    rows = [
        d
        for d in decisions.first_assessed(session, realm.id)
        if d.record["inputs"]["features"]["set_version"] == FEATURE_SET_VERSION
    ]
    chosen = Random(seed).sample(rows, min(sample, len(rows)))
    by_feature: dict[str, int] = {}
    examples: list[dict[str, Any]] = []
    mismatched = 0
    for decision in chosen:
        inputs = decision.record["inputs"]
        stored = inputs["features"]["values"]
        snapshot = ApplicationSnapshot.model_validate(inputs["snapshot"])
        point: Point = "T1" if decision.point == "T1" else "T4"
        fresh = features.compute(
            session, realm, decision.application_id, point, snapshot, decision.as_of, policy, index_key
        ).vector.values
        diff = {name: (stored.get(name), fresh.get(name)) for name in fresh if stored.get(name) != fresh.get(name)}
        if not diff:
            continue
        mismatched += 1
        for name in diff:
            by_feature[name] = by_feature.get(name, 0) + 1
        if len(examples) < EXAMPLES_LIMIT:
            examples.append({"decision_id": str(decision.id), "diff": {k: list(v) for k, v in diff.items()}})
    return PointInTimeReport(len(chosen), mismatched, dict(sorted(by_feature.items())), examples)
