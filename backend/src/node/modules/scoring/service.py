"""Реестр моделей: модель запускается только с совпадающим контрактом признаков."""

from sqlalchemy.orm import Session

from node.modules.scoring import repository
from node.modules.scoring.domain import ScoringOutcome, contract_matches
from shared.errors import ConfigurationError


def evaluate(session: Session, point: str, feature_set_version: str) -> ScoringOutcome:
    models = repository.active(session)
    compatible = [m for m in models if contract_matches(m.points, m.feature_set_version, point, feature_set_version)]
    if not compatible:
        return ScoringOutcome(
            status="no_model",
            reason="contract_mismatch" if models else "registry_empty",
            checked_models=[str(m.id) for m in models],
            scores=[],
        )
    raise ConfigurationError("В реестре есть активная модель, а её загрузка подключается в И2 вместе с обучением")
