"""Роутер модуля: перевод с карты, решение ТАФ по удержанному переводу, лента переводов песочницы."""

from typing import Annotated

from fastapi import APIRouter, Query

from bank_sim.deps import Ctx, Realm
from bank_sim.modules.transfers import service
from bank_sim.modules.transfers.models import Transfer
from bank_sim.modules.transfers.schemas import TransferDecisionIn, TransferIn, TransferOut

router = APIRouter(prefix="/v1/transfers", tags=["Переводы и антифрод банка"])


def _out(t: Transfer) -> TransferOut:
    return TransferOut(
        transfer_id=t.id,
        application_id=t.application_id,
        recipient_card=t.recipient_card,
        amount=t.amount,
        recipient_is_new=t.recipient_is_new,
        balance_before_credit=t.balance_before_credit,
        credit_share=t.credit_share,
        credited_at=t.credited_at,
        status=t.status,
        decided_by=t.decided_by,
        recommendation=t.recommendation,
        node_error=t.node_error,
        own_rule=t.own_rule,
        resolution=t.resolution,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.post("", response_model=TransferOut, status_code=201)
def create(body: TransferIn, ctx: Ctx, realm: Realm) -> TransferOut:
    """ТАФ решает сам: по рекомендации узла (Т3) на первом переводе кредитных денег или своим правилом."""
    return _out(service.create(ctx, realm, body))


@router.post("/{transfer_id}/decision", response_model=TransferOut)
def decide(transfer_id: str, body: TransferDecisionIn, ctx: Ctx, realm: Realm) -> TransferOut:
    return _out(service.decide(ctx, realm, transfer_id, body))


@router.get("", response_model=list[TransferOut])
def list_transfers(
    ctx: Ctx, realm: Realm, application_id: Annotated[str | None, Query(min_length=1, max_length=32)] = None
) -> list[TransferOut]:
    return [_out(t) for t in service.list_for_realm(ctx, realm, application_id)]
