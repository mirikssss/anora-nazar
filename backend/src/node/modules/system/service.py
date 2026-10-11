"""Здоровье узла и его метрики."""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from node.modules.ingest import service as ingest
from node.modules.permits import service as permits


def database_alive(session: Session) -> bool:
    return session.execute(text("SELECT 1")).scalar() == 1


def metrics(session: Session, realm_id: UUID) -> dict[str, Any]:
    """Пометки и их задержка, сигналы после резерва, разрешения по статусам («неизвестно» — резервы без итога)."""
    return {"marks": ingest.metrics(session, realm_id), "permits": permits.counts_by_status(session, realm_id)}
