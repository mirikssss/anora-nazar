"""Обучающая выборка point-in-time: признаки — из записей решений на момент оценки (тот же код, что в решении),
метки — только полученные к дате среза.
"""

import logging
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from node.modules.consortium import service as consortium
from node.modules.consortium.domain import features as network_features
from node.modules.consortium.service import NetworkContext, PastQuery
from node.modules.decisions import service as decisions
from node.modules.features import service as features
from node.modules.features.domain import FEATURE_SET_VERSION, Point, Value
from node.modules.labels import service as labels
from node.modules.labels.models import Label
from node.modules.policy.domain import Policy
from node.modules.realms.domain import RealmContext
from shared.contracts.application import ApplicationSnapshot
from shared.errors import AppError

log = logging.getLogger(__name__)
LEVEL_RANK = {"green": 0, "yellow": 1, "red": 2}


@dataclass(frozen=True)
class Example:
    application_id: UUID
    as_of: datetime
    point: Point
    channel: Literal["online", "program"]
    values: dict[str, Value]
    rules_score: float
    pinfl: str
    supplier: str | None
    identifiers: frozenset[str]
    labels: tuple[Label, ...]


def _rules_score(level: str | None, values: dict[str, Value]) -> float:
    """Базовый уровень без ML (ревью D): уровень правил и графа, внутри уровня — вес редких связей."""
    weight = values.get("rare_links_weight")
    return LEVEL_RANK.get(level or "green", 0) + 0.01 * float(weight or 0)


def identifiers(snapshot: ApplicationSnapshot, labels: list[Label]) -> frozenset[str]:
    """Что связывает заявки в одну группу для строгого разбиения: человек, его идентификаторы, дело."""
    applicant = snapshot.applicant
    keys = {f"pinfl:{applicant.pinfl}", f"phone:{applicant.phone}"}
    if applicant.device_id:
        keys.add(f"device:{applicant.device_id}")
    if applicant.address:
        keys.add(f"address:{' '.join(applicant.address.lower().split())}")
    keys |= {f"case:{label.case_key}" for label in labels if label.case_key}
    return frozenset(keys)


def build(
    session: Session,
    realm: RealmContext,
    cutoff: datetime,
    policy: Policy,
    index_key: bytes,
    network: NetworkContext | None = None,
    now: datetime | None = None,
) -> list[Example]:
    """network — признаки сети на момент оценки от оператора (право history), если в записи решения их нет."""
    rows = decisions.first_assessed(session, realm.visible_ids)
    known: dict[UUID, list[Label]] = {}
    for label in labels.known_as_of(session, realm.visible_ids, [d.application_id for d in rows], cutoff):
        known.setdefault(label.application_id, []).append(label)
    examples = []
    past: list[PastQuery] = []
    for decision in rows:
        inputs = decision.record["inputs"]
        snapshot = ApplicationSnapshot.model_validate(inputs["snapshot"])
        values = inputs["features"]["values"]
        point: Point = "T1" if decision.point == "T1" else "T4"
        if inputs["features"]["set_version"] != FEATURE_SET_VERSION:
            values = features.compute(
                session, realm, decision.application_id, point, snapshot, decision.as_of, policy, index_key
            ).vector.values
        examples.append(
            Example(
                application_id=decision.application_id,
                as_of=decision.as_of,
                point=point,
                channel=snapshot.channel,
                values=values,
                rules_score=_rules_score(decision.level, values),
                pinfl=snapshot.applicant.pinfl,
                supplier=snapshot.program.supplier_inn if snapshot.program else None,
                identifiers=identifiers(snapshot, known.get(decision.application_id, [])),
                labels=tuple(known.get(decision.application_id, [])),
            )
        )
        if inputs.get("network", {}).get("status") != "ok":
            sandbox = decision.realm_id if decision.realm_id != realm.world_id else None
            past.append(PastQuery(decision.application_id, decision.as_of, snapshot, sandbox))
    if network is not None and past:
        examples = _with_network(session, network, examples, past, now or cutoff)
    return sorted(examples, key=lambda e: e.as_of)


def _with_network(
    session: Session, network: NetworkContext, examples: list[Example], past: list[PastQuery], now: datetime
) -> list[Example]:
    """Ретро-ответы сети: та же функция признаков, что в решении; оператор недоступен — признаки сети пустые."""
    try:
        answers = consortium.history_observations(session, network, past, now)
    except AppError as exc:
        log.warning("Ответы сети для обучения не получены: %s", exc.message)
        return examples
    return [
        replace(e, values=e.values | network_features(answers[(e.application_id, e.as_of)]))
        if (e.application_id, e.as_of) in answers
        else e
        for e in examples
    ]


def gender(pinfl: str) -> str:
    """Пол из первой цифры ПИНФЛ — только для проверки справедливости, не признак модели."""
    return "male" if int(pinfl[0]) % 2 == 1 else "female"


def birth_date(pinfl: str) -> date:
    century = {"1": 1800, "2": 1800, "3": 1900, "4": 1900, "5": 2000, "6": 2000}[pinfl[0]]
    return date(century + int(pinfl[5:7]), int(pinfl[3:5]), int(pinfl[1:3]))


def age_band(pinfl: str, on: date, bands: list[int]) -> str:
    born = birth_date(pinfl)
    age = on.year - born.year - ((on.month, on.day) < (born.month, born.day))
    lower = 0
    for edge in bands:
        if age < edge:
            return f"{lower}-{edge - 1}"
        lower = edge
    return f"{lower}+"
