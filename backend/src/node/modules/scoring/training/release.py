"""Выпуск версии модели в контуре: запрос одного риск-менеджера, подтверждение другого, запись в журнал."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from node.modules.audit import service as audit
from node.modules.scoring import repository
from node.modules.scoring.models import ModelRelease
from shared.errors import ConflictError, ForbiddenError, NotFoundError


def request(session: Session, realm_id: UUID, model_id: UUID, staff_code: str, now: datetime) -> ModelRelease:
    version = repository.get(session, model_id)
    if version is None or version.realm_id not in (None, realm_id):  # чужая песочница не видна
        raise NotFoundError("model_not_found", "Версия модели не найдена")
    release = ModelRelease(
        id=uuid4(),
        realm_id=realm_id,
        model_version_id=version.id,
        model_name=version.name,
        requested_by=staff_code,
        requested_at=now,
        approved_by=None,
        approved_at=None,
    )
    repository.add(session, release)
    session.flush()  # подтверждение может прийти в той же транзакции (команда стенда)
    audit.append(
        session,
        realm_id,
        "model.release_requested",
        {"release_id": str(release.id), "model_version_id": str(version.id), "requested_by": staff_code},
        now,
    )
    return release


def approve(session: Session, realm_id: UUID, release_id: UUID, staff_code: str, now: datetime) -> ModelRelease:
    release = repository.release_for_update(session, release_id)
    if release is None or release.realm_id != realm_id:
        raise NotFoundError("release_not_found", "Запрос на выпуск не найден")
    if release.approved_at is not None:
        raise ConflictError("release_already_approved", "Выпуск уже подтверждён")
    if release.requested_by == staff_code:
        raise ForbiddenError("second_signer_required", "Подтверждает другой сотрудник: нужен второй подписант")
    release.approved_by, release.approved_at = staff_code, now
    audit.append(
        session,
        realm_id,
        "model.released",
        {
            "release_id": str(release.id),
            "model_version_id": str(release.model_version_id),
            "requested_by": release.requested_by,
            "approved_by": staff_code,
        },
        now,
    )
    return release
