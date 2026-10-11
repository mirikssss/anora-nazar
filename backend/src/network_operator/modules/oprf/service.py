"""Вычисления OPRF: квота кредитора, журнал запроса и применение ключа — в одной транзакции."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from network_operator.modules.activity import service as activity
from network_operator.modules.clients.domain import Caller
from network_operator.modules.oprf.domain import KeyRing
from network_operator.modules.oprf.schemas import EvaluationIn, EvaluationOut
from network_operator.modules.quotas import service as quotas
from network_operator.settings import QuotasConfig
from shared.errors import ForbiddenError, ValidationFailedError
from shared.network.oprf import OprfError


def _ensure_allowance(
    session: Session, caller: Caller, realm_id: UUID | None, requested: int, limits: QuotasConfig, now: datetime
) -> None:
    """Квота кредитора в контуре; проверки одного кредитора идут по очереди, чтобы параллельные пакеты не обошли её."""
    if caller.lender is None:
        raise ForbiddenError("lender_required", "OPRF вычисляется только для кредитора")
    quotas.lock(session, caller.lender, realm_id)
    applications = activity.applications_since(session, caller.lender, realm_id, quotas.window_start(limits, now))
    quotas.ensure_oprf_allowance(session, caller.lender, realm_id, requested, applications, limits, now)


def evaluate(
    session: Session,
    caller: Caller,
    realm_id: UUID | None,
    body: EvaluationIn,
    keys: KeyRing,
    limits: QuotasConfig,
    now: datetime,
) -> EvaluationOut:
    if not caller.history:
        _ensure_allowance(session, caller, realm_id, len(body.blinded), limits, now)
    try:
        evaluated = keys.evaluate(body.kind, [bytes.fromhex(b) for b in body.blinded])
    except OprfError as exc:
        raise ValidationFailedError("invalid_element", "Ослеплённый элемент — не элемент группы ristretto255") from exc
    quotas.log(session, caller, realm_id, now, operation="oprf", items=1, tokens=len(body.blinded))
    return EvaluationOut(kind=body.kind, key_version=keys.version(body.kind), evaluated=[e.hex() for e in evaluated])
