"""Чистая логика меток (Блок 3, «Метки»): какой факт даёт какую метку и можно ли на ней учить.

Позитив — подтверждённый фрод или подтверждённое воздействие; сильный негатив — ложное срабатывание после
проверки; слабый негатив — кредит, созревший без пропусков. «Не подтвердилось» и всё, что выведено по графу, —
не метки.
"""

from dataclasses import dataclass
from typing import Any, Literal

from shared.contracts.facts import IncidentRecorded, LoanMatured

LabelKind = Literal["positive", "strong_negative", "weak_negative"]

INCIDENT_RESULTS: dict[str, LabelKind] = {
    "confirmed_fraud": "positive",
    "confirmed_coercion": "positive",
    "false_positive": "strong_negative",
}


@dataclass(frozen=True)
class LabelDraft:
    application_external_ids: tuple[str, ...]
    typology: str | None
    kind: LabelKind
    source: str
    confirmation: str
    case_key: str | None


def from_fact(fact_type: str, payload: dict[str, Any]) -> LabelDraft | None:
    if fact_type == "incident.recorded":
        incident = IncidentRecorded.model_validate(payload)
        kind = INCIDENT_RESULTS.get(incident.result)
        if kind is None:
            return None
        return LabelDraft(
            application_external_ids=tuple(incident.application_ids),
            typology=incident.typology,
            kind=kind,
            source=incident.kind,
            confirmation="confirmed",
            case_key=incident.case_key,
        )
    if fact_type == "loan.matured":
        matured = LoanMatured.model_validate(payload)
        if matured.missed_payments > 0:
            return None
        return LabelDraft(
            application_external_ids=(matured.application_id,),
            typology=None,
            kind="weak_negative",
            source="core_banking",
            confirmation="matured",
            case_key=None,
        )
    return None
