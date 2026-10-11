"""Запуски обучения из контура: петля «исход дела → метка → обучение → тень → выпуск вторым подписантом».

Риск-менеджер ставит запуск в очередь; фоновый обработчик обучает модели на метках общего мира и своей песочницы.
Новые версии видны только этому контуру и идут в тень, выпуск — через двух подписантов.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from node.modules.audit import service as audit
from node.modules.consortium.service import NetworkContext
from node.modules.policy.domain import Policy
from node.modules.realms import service as realms
from node.modules.realms.domain import RealmContext
from node.modules.scoring import repository
from node.modules.scoring.models import TrainingRun
from node.modules.scoring.training import pipeline
from node.modules.scoring.training.config import TrainingConfig
from shared.db import Database
from shared.errors import ConflictError


def request(session: Session, realm: RealmContext, staff: str, now: datetime) -> TrainingRun:
    if repository.active_run(session, realm.id) is not None:
        raise ConflictError("training_in_progress", "Обучение в этом контуре уже идёт")
    run = TrainingRun(
        id=uuid4(),
        realm_id=realm.id,
        requested_by=staff,
        status="queued",
        requested_at=now,
        started_at=None,
        finished_at=None,
        versions=[],
        error=None,
    )
    repository.add(session, run)
    audit.append(session, realm.id, "model.training_requested", {"run_id": str(run.id), "by": staff}, now)
    return run


def runs(session: Session, realm: RealmContext) -> list[TrainingRun]:
    return repository.runs(session, realm.id)


def process_next(
    db: Database,
    cfg: TrainingConfig,
    policy: Policy,
    index_key: bytes,
    now: datetime,
    network: NetworkContext | None = None,
) -> bool:
    """Один запуск из очереди. Обучение — в своей транзакции; ошибка записывается в запуск, а не теряется."""
    with db.transaction() as session:
        run = repository.next_queued_run(session)
        if run is None:
            return False
        run.status, run.started_at = "running", now
        run_id, realm_id = run.id, run.realm_id
    try:
        with db.transaction() as session:
            realm = realms.resolve(session, realm_id, now)
            result = pipeline.run(session, realm, cfg, policy, index_key, now, network)
            run = session.get(TrainingRun, run_id)
            assert run is not None
            run.status, run.finished_at = "done", now
            run.versions = [str(v.id) for v in result.versions]
            audit.append(session, realm_id, "model.trained", {"run_id": str(run_id), "versions": run.versions}, now)
    except Exception as exc:
        with db.transaction() as session:
            failed = session.get(TrainingRun, run_id)
            if failed is not None:
                failed.status, failed.finished_at, failed.error = "failed", now, str(exc)[:2000]
        raise
    return True
