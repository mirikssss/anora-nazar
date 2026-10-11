"""Запрос счётчиков: версии чужих событий и результаты проверок по токенам — одним чтением на пакет, счёт —
чистой функцией; запрос с watch_until подписывает заявку на её токены."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from network_operator.modules.activity import service as activity
from network_operator.modules.activity.domain import token_key
from network_operator.modules.clients.domain import Caller
from network_operator.modules.confirmed import service as confirmed
from network_operator.modules.counters import domain
from network_operator.modules.counters.domain import QueryTokens
from network_operator.modules.counters.schemas import CountersIn, CountersOut
from network_operator.modules.quotas import service as quotas
from network_operator.modules.watches import service as watches
from network_operator.settings import OperatorConfig
from shared.contracts.network import CounterQuery, CounterResult
from shared.errors import ForbiddenError, ValidationFailedError


def _query_tokens(caller_lender: str, query: CounterQuery, now: datetime) -> QueryTokens:
    tokens = list(dict.fromkeys([token_key(query.subject), *(token_key(t) for t in query.tokens)]))
    return QueryTokens(requester=caller_lender, applicant=query.subject.token, tokens=tokens, as_of=query.as_of or now)


def _validate(caller: Caller, body: CountersIn, now: datetime, can_watch: bool) -> str:
    if caller.lender is None:
        raise ForbiddenError("lender_required", "Счётчики спрашивает только кредитор")
    if not caller.history and any(q.as_of is not None for q in body.queries):
        raise ForbiddenError("history_required", "as_of в запросе — только с правом history")
    watching = [q for q in body.queries if q.watch_until is not None]
    if watching and not can_watch:
        raise ValidationFailedError("callback_not_configured", "Кредитору некуда доставлять уведомления о совпадениях")
    if any(q.watch_until is not None and q.watch_until <= now for q in watching):
        raise ValidationFailedError("watch_in_past", "watch_until — момент в будущем")
    return caller.lender


def query(
    session: Session,
    caller: Caller,
    realm_id: UUID | None,
    body: CountersIn,
    config: OperatorConfig,
    now: datetime,
    *,
    can_watch: bool,
) -> CountersOut:
    lender = _validate(caller, body, now, can_watch)
    windows = config.counters.durations()
    queries = [_query_tokens(lender, q, now) for q in body.queries]
    tokens = list(dict.fromkeys(t for q in queries for t in q.tokens))
    oldest = min(q.as_of for q in queries) - max(windows.values(), default=timedelta(0))
    latest = max(q.as_of for q in queries)
    versions = activity.matching(session, realm_id, lender, tokens, oldest, latest)
    facts = confirmed.matching(session, realm_id, lender, tokens, latest)
    results = [
        CounterResult(
            ref=raw.ref,
            as_of=q.as_of,
            counters=domain.counters(q, versions, windows),
            confirmed=domain.confirmed_matches(q, facts),
        )
        for raw, q in zip(body.queries, queries, strict=True)
    ]
    for raw, q in zip(body.queries, queries, strict=True):
        if raw.watch_until is not None:
            until = watches.capped_until(raw.watch_until, now, config.watches.max_seconds)
            watches.subscribe(
                session, lender=lender, realm_id=realm_id, ref=raw.ref, tokens=q.tokens, until=until, now=now
            )
    kinds = {t[0] for t in tokens}
    quotas.log(
        session,
        caller,
        realm_id,
        now,
        operation="query",
        items=len(body.queries),
        tokens=len(tokens),
        counters=domain.counter_names_for(kinds),
    )
    return CountersOut(results=results)
