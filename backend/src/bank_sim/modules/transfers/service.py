"""Переводы с карт и транзакционный антифрод банка (№ 3759 п. 37): на первом переводе кредитных денег ТАФ
спрашивает рекомендацию узла (Т3) и решает сам; узел недоступен — решает своим правилом (ревью A)."""

from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from bank_sim.context import BankContext
from bank_sim.modules.cards import service as cards
from bank_sim.modules.conveyor import service as conveyor
from bank_sim.modules.failures import service as failures
from bank_sim.modules.failures.schemas import Flags
from bank_sim.modules.transfers import domain, repository
from bank_sim.modules.transfers.domain import DecidedBy, NodeRecommendation, TransferStatus
from bank_sim.modules.transfers.models import Transfer
from bank_sim.modules.transfers.schemas import TransferDecisionIn, TransferIn
from shared.contracts.transfers import TransferRecommendationIn
from shared.errors import AppError, ConflictError, NotFoundError, ValidationFailedError

HELD: TransferStatus = "held"
EXECUTED: TransferStatus = "executed"


def _ask_node(
    ctx: BankContext, realm_id: UUID, request: TransferRecommendationIn, flags: Flags
) -> tuple[NodeRecommendation | None, dict[str, Any] | None]:
    """Рекомендация узла или причина, по которой её нет: сбой узла — не разрешение, ТАФ решает сам."""
    try:
        failures.ensure_node_reachable(flags)
        raw = ctx.node.recommend_transfer(realm_id, request.model_dump(mode="json"), request.transfer_id)
        return NodeRecommendation.model_validate(raw), None
    except AppError as exc:
        return None, {"code": exc.code, "message": exc.message}
    except ValidationError:
        return None, {"code": "invalid_recommendation", "message": "Узел ответил не по контракту Т3"}


def create(ctx: BankContext, realm_id: UUID, body: TransferIn) -> Transfer:
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        app = conveyor.get(session, realm_id, body.application_id)
        credit = cards.credit_for(session, realm_id, app.external_id)
        if credit is None:
            raise ConflictError("credit_not_disbursed", "Перевод кредитных денег возможен только после зачисления")
        if cards.balance(session, realm_id, credit.account) < body.amount:
            raise ValidationFailedError("insufficient_funds", "На карте недостаточно средств для перевода")
        recipient_is_new = not cards.is_known_recipient(session, realm_id, credit.pinfl, body.recipient_card)
        first = not repository.has_executed(session, realm_id, app.external_id)
        flags = failures.flags(session, realm_id)
        account, pinfl = credit.account, credit.pinfl
        balance_before, credited_at = credit.balance_before, credit.credited_at

    transfer_id = f"TRF-{uuid4().hex[:12].upper()}"
    recommendation, node_error = None, None
    if first:
        request = TransferRecommendationIn(
            application_id=app.external_id,
            transfer_id=transfer_id,
            amount=body.amount,
            recipient_card=body.recipient_card,
            recipient_is_new=recipient_is_new,
            balance_before_credit=balance_before,
            credited_at=credited_at,
            requested_at=now,
        )
        recommendation, node_error = _ask_node(ctx, realm_id, request, flags)

    rule = ctx.config.transfers.own_rule
    status = domain.status_from_recommendation(recommendation)
    decided_by: DecidedBy = "node"
    own_rule: dict[str, Any] | None = None
    if status is None:
        result = domain.apply_own_rule(
            rule,
            amount=body.amount,
            balance_before_credit=balance_before,
            recipient_is_new=recipient_is_new,
            credited_at=credited_at,
            now=now,
        )
        status = HELD if result.hold else EXECUTED
        decided_by = "own_rule"
        own_rule = result.as_record(rule)

    with ctx.db.transaction() as session:
        if status == EXECUTED:
            cards.debit(
                session,
                realm_id,
                account=account,
                pinfl=pinfl,
                recipient_card=body.recipient_card,
                amount=body.amount,
                now=now,
            )
        transfer = Transfer(
            id=transfer_id,
            realm_id=realm_id,
            application_id=app.external_id,
            pinfl=pinfl,
            account=account,
            recipient_card=body.recipient_card,
            amount=body.amount,
            recipient_is_new=recipient_is_new,
            balance_before_credit=balance_before,
            credit_share=domain.credit_share(body.amount, balance_before),
            credited_at=credited_at,
            status=status,
            decided_by=decided_by,
            recommendation=None if recommendation is None else recommendation.model_dump(mode="json"),
            node_error=node_error,
            own_rule=own_rule,
            resolution=None,
            created_at=now,
            updated_at=now,
        )
        repository.add(session, transfer)
    return transfer


def decide(ctx: BankContext, realm_id: UUID, transfer_id: str, body: TransferDecisionIn) -> Transfer:
    """ТАФ банка подтвердил перевод с клиентом — исполнить, или отменить. Только для удержанного перевода."""
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        transfer = repository.get(session, realm_id, transfer_id, lock=True)
        if transfer is None:
            raise NotFoundError("transfer_not_found", "Перевод не найден")
        if transfer.status != HELD:
            raise ConflictError("transfer_not_held", "Решение нужно только по удержанному переводу")
        status: TransferStatus = "cancelled"
        if body.action == "release":
            cards.debit(
                session,
                realm_id,
                account=transfer.account,
                pinfl=transfer.pinfl,
                recipient_card=transfer.recipient_card,
                amount=transfer.amount,
                now=now,
            )
            status = EXECUTED
        transfer.status, transfer.resolution, transfer.updated_at = status, body.action, now
        return transfer


def list_for_realm(ctx: BankContext, realm_id: UUID, application_id: str | None) -> list[Transfer]:
    with ctx.db.transaction() as session:
        return repository.list_for_realm(session, realm_id, application_id)
