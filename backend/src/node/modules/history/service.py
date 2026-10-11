"""Прогон элементов истории по одному: каждая оценка и каждое событие — своя транзакция, как в живом пути."""

from collections import Counter
from collections.abc import Callable, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from node.context import NodeContext
from node.modules.decisions import service as decisions
from node.modules.decisions.schemas import AssessmentIn
from node.modules.ingest import service as ingest
from node.modules.realms import service as realms
from node.modules.realms.domain import RealmContext
from shared.contracts.history import HistoryAssessment, HistoryEvent
from shared.errors import ValidationFailedError


def _replayable[T](work: Callable[[Session], T]) -> Callable[[Session], T]:
    """Прогон истории идемпотентен и повторяем с начала, поэтому коммит не ждёт сброса журнала на диск."""

    def wrapped(session: Session) -> T:
        session.execute(text("SET LOCAL synchronous_commit = off"))
        return work(session)

    return wrapped


def _world(ctx: NodeContext) -> RealmContext:
    with ctx.db.transaction() as session:
        return realms.resolve(session, realms.world_id(session), ctx.clock.now())


def _assess(ctx: NodeContext, realm: RealmContext, item: HistoryAssessment) -> str:
    body = AssessmentIn(
        point=item.point,
        application_id=item.application_id,
        application_version=item.application_version,
        occurred_at=item.occurred_at,
        snapshot=item.snapshot,
    )
    key = f"history:{item.application_id}:{item.application_version}"
    assessing = ctx.assessing()
    ctx.db.run(_replayable(lambda session: decisions.assess(session, assessing, realm, body, key, item.received_at)))
    return "assessed"


def _receive(ctx: NodeContext, realm: RealmContext, item: HistoryEvent) -> str:
    intake = ctx.intake()
    return ctx.db.run(
        _replayable(lambda session: ingest.receive(session, intake, realm, item.envelope, item.received_at))
    )


def run(ctx: NodeContext, items: Sequence[HistoryAssessment | HistoryEvent]) -> Counter[str]:
    if len(items) > ctx.config.history.max_batch:
        raise ValidationFailedError(
            "history_batch_too_large", f"В одном запросе до {ctx.config.history.max_batch} элементов истории"
        )
    world = _world(ctx)
    outcomes: Counter[str] = Counter()
    for item in items:
        outcome = _assess(ctx, world, item) if isinstance(item, HistoryAssessment) else _receive(ctx, world, item)
        outcomes[outcome] += 1
    return outcomes
