"""Доступ к таблицам модуля."""

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from node.modules.scoring.models import ModelRelease, ModelVersion, TrainingRun


def add(session: Session, row: ModelVersion | ModelRelease | TrainingRun) -> None:
    session.add(row)


def get(session: Session, model_id: UUID) -> ModelVersion | None:
    return session.get(ModelVersion, model_id)


def get_many(session: Session, ids: Iterable[UUID]) -> list[ModelVersion]:
    ids = list(set(ids))
    if not ids:
        return []
    return list(session.scalars(select(ModelVersion).where(ModelVersion.id.in_(ids))))


def all_versions(session: Session, realm_ids: Iterable[UUID]) -> list[ModelVersion]:
    """Версии, обученные в общем мире или в этом контуре: чужие песочницы не видны."""
    ids = list(realm_ids)
    return list(
        session.scalars(
            select(ModelVersion)
            .where((ModelVersion.realm_id.is_(None)) | (ModelVersion.realm_id.in_(ids)))
            .order_by(ModelVersion.created_at.desc())
        )
    )


def approved_releases(session: Session, realm_ids: Iterable[UUID]) -> list[ModelRelease]:
    return list(
        session.scalars(
            select(ModelRelease)
            .where(ModelRelease.realm_id.in_(list(realm_ids)), ModelRelease.approved_at.is_not(None))
            .order_by(ModelRelease.approved_at)
        )
    )


def release_for_update(session: Session, release_id: UUID) -> ModelRelease | None:
    return session.scalars(select(ModelRelease).where(ModelRelease.id == release_id).with_for_update()).one_or_none()


def pending_releases(session: Session, realm_id: UUID) -> list[ModelRelease]:
    return list(
        session.scalars(
            select(ModelRelease).where(ModelRelease.realm_id == realm_id, ModelRelease.approved_at.is_(None))
        )
    )


def next_queued_run(session: Session) -> TrainingRun | None:
    return session.scalars(
        select(TrainingRun)
        .where(TrainingRun.status == "queued")
        .order_by(TrainingRun.requested_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).one_or_none()


def runs(session: Session, realm_id: UUID) -> list[TrainingRun]:
    return list(
        session.scalars(
            select(TrainingRun).where(TrainingRun.realm_id == realm_id).order_by(TrainingRun.requested_at.desc())
        )
    )


def active_run(session: Session, realm_id: UUID) -> TrainingRun | None:
    return session.scalars(
        select(TrainingRun).where(TrainingRun.realm_id == realm_id, TrainingRun.status.in_(("queued", "running")))
    ).first()
