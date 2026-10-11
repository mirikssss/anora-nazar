"""Доступ к таблицам модуля."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from node.modules.scoring.models import ModelVersion


def active(session: Session) -> list[ModelVersion]:
    return list(session.scalars(select(ModelVersion).where(ModelVersion.status == "active")))
