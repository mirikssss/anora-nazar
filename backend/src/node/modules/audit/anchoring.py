"""Отправка контрольных точек в якорь и чтение якорей. Сеть — вне транзакций базы."""

from uuid import UUID

from node.modules.audit.domain import checkpoint_payload
from node.modules.audit.models import AuditCheckpoint
from shared.errors import AppError
from shared.http import ServiceClient


def send(client: ServiceClient, checkpoint: AuditCheckpoint) -> str | None:
    """Возвращает текст ошибки или None, если якорь принял точку."""
    body = {
        **checkpoint_payload(
            checkpoint.realm_id, checkpoint.seq, checkpoint.merkle_root, checkpoint.head_hash, checkpoint.created_at
        ),
        "signature": checkpoint.signature,
        "key_id": checkpoint.key_id,
    }
    try:
        client.call("POST", "/v1/checkpoints", json=body)
    except AppError as exc:
        return exc.message
    return None


def anchored_roots(client: ServiceClient, realm_id: UUID) -> dict[int, str] | None:
    """Корни, которые хранит якорь; None — якорь недоступен."""
    try:
        body = client.call("GET", "/v1/checkpoints", params={"realm_id": str(realm_id)})
    except AppError:
        return None
    return {int(item["seq"]): str(item["merkle_root"]) for item in body["items"]}
