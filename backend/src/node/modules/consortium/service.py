"""Адаптер сети кредиторов: токены, запрос счётчиков, события активности, результаты дел, уведомления.

Сеть — отдельная интеграция, выключена по умолчанию (политика, раздел network). Узел полностью работает без неё:
выключена — в сеть не уходит ничего; не ответила — решение по своим признакам с причиной «сеть недоступна».
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from node.modules.applications import service as applications
from node.modules.audit import service as audit
from node.modules.consortium import repository
from node.modules.consortium.domain import NetworkObservation, application_identifiers
from node.modules.index.domain import keyed
from node.modules.outbox import service as outbox
from node.modules.policy.domain import Policy
from node.modules.realms.domain import RealmContext
from node.settings import OutboxConfig
from shared.contracts.application import ApplicationSnapshot
from shared.contracts.network import (
    CONTRACT_VERSION,
    ActivityEvent,
    ConfirmedResult,
    CounterQuery,
    MatchNotification,
    TokenKind,
    TokenRef,
)
from shared.errors import AppError, ConfigurationError
from shared.network.client import NetworkClient
from shared.network.normalize import normalize

ACTIVITY = "network.activity"
TOGGLE_PATH = "network.enabled"
CONFIRMED = "network.confirmed"
Tokens = dict[tuple[TokenKind, str], TokenRef]


@dataclass(frozen=True)
class NetworkContext:
    client: NetworkClient | None  # None — адрес оператора не задан: включённая сеть всегда «недоступна»
    history: NetworkClient | None  # право history: ответы на прошлые моменты для обучения
    index_key: bytes
    outbox: OutboxConfig


def operator_realm(realm: RealmContext) -> UUID | None:
    """У оператора общий мир — без контура, песочница — своим идентификатором."""
    return realm.id if realm.is_sandbox else None


def enabled(policy: Policy) -> bool:
    return policy.network is not None and policy.network.enabled


def tokenize(
    session: Session,
    ctx: NetworkContext,
    client: NetworkClient,
    sandbox: UUID | None,
    items: list[tuple[TokenKind, str]],
    now: datetime,
) -> Tokens:
    """Токены через кеш: OPRF спрашивается только для новых значений (квота оператора — по реальным заявкам)."""
    keys = {(kind, value): keyed(ctx.index_key, kind, normalize(kind, value)) for kind, value in items}
    cached = repository.cached_tokens(session, [(kind, key) for (kind, _), key in keys.items()])
    tokens: Tokens = {}
    missing: list[tuple[TokenKind, str]] = []
    for (kind, value), key in keys.items():
        row = cached.get((kind, key))
        if row is None:
            missing.append((kind, value))
        else:
            tokens[(kind, value)] = TokenRef(kind=kind, key_version=row.key_version, token=row.token)
    if missing:
        fresh = client.tokenize(sandbox, missing)
        tokens.update(fresh)
        repository.save_tokens(session, _token_rows(fresh, keys, now))
    return tokens


def _token_rows(fresh: Tokens, keys: dict[tuple[TokenKind, str], str], now: datetime) -> list[dict[str, Any]]:
    return [
        {
            "kind": ref.kind,
            "value_key": keys[item],
            "key_version": ref.key_version,
            "token": ref.token,
            "created_at": now,
        }
        for item, ref in fresh.items()
    ]


def _query(
    session: Session,
    ctx: NetworkContext,
    client: NetworkClient | None,
    realm: RealmContext,
    ref: str,
    items: list[tuple[TokenKind, str]],
    as_of: datetime | None,
    watch_until: datetime | None,
    now: datetime,
) -> tuple[NetworkObservation, Tokens]:
    if client is None:
        return NetworkObservation(status="unavailable", as_of=as_of, error="network_not_configured"), {}
    try:
        tokens = tokenize(session, ctx, client, operator_realm(realm), items, now)
        subject = next(t for (kind, _), t in tokens.items() if kind == "pinfl")
        others = [t for (kind, _), t in tokens.items() if kind != "pinfl"]
        query = CounterQuery(ref=ref, subject=subject, tokens=others, as_of=as_of, watch_until=watch_until)
        result = client.query(operator_realm(realm), [query])[0]
    except AppError as exc:
        return NetworkObservation(status="unavailable", as_of=as_of, error=exc.code), {}
    observation = NetworkObservation(
        status="ok", as_of=result.as_of, counters=result.counters, confirmed=result.confirmed
    )
    return observation, tokens


def observe(
    session: Session,
    ctx: NetworkContext,
    realm: RealmContext,
    app_id: UUID,
    snapshot: ApplicationSnapshot,
    policy: Policy,
    watch_until: datetime,
    now: datetime,
) -> tuple[NetworkObservation, Tokens]:
    """Ответ сети на момент решения; подписка на новые совпадения — до конца срока годности оценки."""
    if not enabled(policy):
        return NetworkObservation(status="disabled"), {}
    items = application_identifiers(snapshot)
    return _query(session, ctx, ctx.client, realm, str(app_id), items, None, watch_until, now)


def observe_card(
    session: Session,
    ctx: NetworkContext,
    realm: RealmContext,
    app_id: UUID,
    pinfl: str,
    card: str,
    policy: Policy,
    now: datetime,
) -> tuple[NetworkObservation, Tokens]:
    """Т3: заёмщики и кредиторы с этой картой-получателем у других банков, совпадение с их делами."""
    if not enabled(policy):
        return NetworkObservation(status="disabled"), {}
    items: list[tuple[TokenKind, str]] = [("pinfl", pinfl), ("card", card)]
    return _query(session, ctx, ctx.client, realm, str(app_id), items, None, None, now)


def _enqueue(
    session: Session, ctx: NetworkContext, realm: RealmContext, topic: str, body: dict[str, Any], now: datetime
) -> None:
    realm_ref = operator_realm(realm)
    payload = {"realm": str(realm_ref) if realm_ref else None, "body": body}
    outbox.enqueue(session, ctx.outbox, realm.id, topic, payload, now)


def _subject_and_rest(tokens: Tokens) -> tuple[TokenRef, list[TokenRef]]:
    subject = next(t for (kind, _), t in tokens.items() if kind == "pinfl")
    return subject, [t for (kind, _), t in tokens.items() if kind != "pinfl"]


def report_application(
    session: Session,
    ctx: NetworkContext,
    realm: RealmContext,
    app_id: UUID,
    version: int,
    channel: str,
    tokens: Tokens,
    first: bool,
    occurred_at: datetime,
    now: datetime,
) -> None:
    """Событие заявки идёт до любой проверки; новая версия — исправление первого события, человек тот же."""
    subject, rest = _subject_and_rest(tokens)
    original = f"{app_id}:application"
    event = ActivityEvent(
        event_id=original if first else f"{original}:v{version}",
        kind="application" if first else "correction",
        occurred_at=occurred_at,
        channel="online" if channel == "online" else "program",
        subject=subject,
        tokens=rest,
        refers_to=None if first else original,
    )
    _enqueue(session, ctx, realm, ACTIVITY, event.model_dump(mode="json"), now)


def report_issuance(
    session: Session,
    ctx: NetworkContext,
    realm: RealmContext,
    app_id: UUID,
    snapshot: ApplicationSnapshot,
    occurred_at: datetime,
    now: datetime,
) -> None:
    items: list[tuple[TokenKind, str]] = [("pinfl", snapshot.applicant.pinfl)]
    if snapshot.program is not None:
        items.append(("supplier_inn", snapshot.program.supplier_inn))
    client = ctx.client
    if client is None:
        raise ConfigurationError("Сеть включена, но адрес оператора не задан")
    subject, rest = _subject_and_rest(tokenize(session, ctx, client, operator_realm(realm), items, now))
    event = ActivityEvent(
        event_id=f"{app_id}:issuance",
        kind="issuance",
        occurred_at=occurred_at,
        channel=snapshot.channel,
        subject=subject,
        tokens=rest,
    )
    _enqueue(session, ctx, realm, ACTIVITY, event.model_dump(mode="json"), now)


def report_transfer(
    session: Session,
    ctx: NetworkContext,
    realm: RealmContext,
    transfer_id: str,
    tokens: Tokens,
    credit_share: float,
    occurred_at: datetime,
    now: datetime,
) -> None:
    subject, rest = _subject_and_rest(tokens)
    event = ActivityEvent(
        event_id=f"transfer:{transfer_id}",
        kind="transfer",
        occurred_at=occurred_at,
        subject=subject,
        tokens=rest,
        credit_share=min(1.0, max(0.0, credit_share)),
    )
    _enqueue(session, ctx, realm, ACTIVITY, event.model_dump(mode="json"), now)


def report_confirmed(
    session: Session,
    ctx: NetworkContext,
    realm: RealmContext,
    result_id: str,
    typology: str,
    confirmation: str,
    items: list[tuple[TokenKind, str]],
    card_keys: list[str],
    confirmed_at: datetime,
) -> int:
    """Результат закрытого дела: только идентификаторы мошенника — что именно, решает вызывающий по исходу (Блок 4).

    Карты-получатели известны узлу только ключом индекса; их токены берутся из кеша — они получены на Т3.
    """
    client = ctx.client
    if client is None:
        raise ConfigurationError("Сеть включена, но адрес оператора не задан")
    tokens = list(tokenize(session, ctx, client, operator_realm(realm), items, confirmed_at).values()) if items else []
    cached = repository.cached_tokens(session, [("card", key) for key in card_keys])
    tokens += [TokenRef(kind="card", key_version=row.key_version, token=row.token) for row in cached.values()]
    if not tokens:
        return 0
    result = ConfirmedResult(
        result_id=result_id,
        typology=typology,
        confirmation="confirmed_coercion" if confirmation == "confirmed_coercion" else "confirmed_fraud",
        tokens=tokens,
        confirmed_at=confirmed_at,
    )
    _enqueue(session, ctx, realm, CONFIRMED, result.model_dump(mode="json"), confirmed_at)
    return len(tokens)


def deliver(client: NetworkClient | None, messages: list[dict[str, Any]]) -> None:
    """Отправка outbox оператору пачками по контуру и потоку; ошибка — сообщения уйдут на следующем такте."""
    if client is None:
        raise ConfigurationError("Адрес оператора сети не задан")
    batches: dict[tuple[str | None, str], list[dict[str, Any]]] = defaultdict(list)
    for message in messages:
        payload = message["payload"]
        batches[(payload["realm"], message["topic"])].append(payload["body"])
    for (realm, topic), bodies in batches.items():
        realm_id = UUID(realm) if realm else None
        if topic == ACTIVITY:
            client.send_activity(realm_id, [ActivityEvent.model_validate(b) for b in bodies])
        else:
            client.send_confirmed(realm_id, [ConfirmedResult.model_validate(b) for b in bodies])


def on_notification(
    session: Session, ctx: NetworkContext, realm: RealmContext, body: MatchNotification, now: datetime
) -> str:
    """Новое совпадение у другого кредитора: открытая заявка своего контура помечается «нужна новая оценка»."""
    app_id = _open_application(session, realm, body.ref, now)
    outcome = "marked" if app_id is not None else "ignored"
    row = {
        "notification_id": body.notification_id,
        "realm_id": realm.id,
        "application_id": app_id,
        "kinds": list(body.kinds),
        "outcome": outcome,
        "received_at": now,
    }
    if not repository.record_notification(session, row):
        return "duplicate"
    if app_id is None:
        return outcome
    locked = applications.lock(session, {app_id})
    cause = {"network_match": list(body.kinds), "notification_id": body.notification_id, "at": now.isoformat()}
    marked = applications.mark_for_reassessment(session, realm.id, set(locked), cause, now)
    for marked_id in marked:
        event = {"application_id": locked[marked_id].external_id, "cause": cause, "kinds": list(body.kinds)}
        outbox.enqueue(session, ctx.outbox, realm.id, "application.reassessment_required", event, now)
    audit.append(
        session,
        realm.id,
        "network.match_received",
        {"applications": [locked[a].external_id for a in marked], "kinds": list(body.kinds)},
        now,
    )
    return outcome


def _open_application(session: Session, realm: RealmContext, ref: str, now: datetime) -> UUID | None:
    try:
        app_id = UUID(ref)
    except ValueError:
        return None
    return app_id if app_id in applications.open_ids(session, realm.id, {app_id}, now) else None


@dataclass(frozen=True)
class PastQuery:
    """Запрос ответа сети на прошлый момент: заявка, её момент оценки и контур у оператора."""

    application_id: UUID
    as_of: datetime
    snapshot: ApplicationSnapshot
    sandbox: UUID | None


def history_observations(
    session: Session, ctx: NetworkContext, requests: list[PastQuery], now: datetime
) -> dict[tuple[UUID, datetime], NetworkObservation]:
    """Ответ сети на прошлый момент — для признаков сети в обучении и абляции «+ сеть».

    Оператор считает по событиям, полученным до as_of (point-in-time), — та же функция признаков, что в решении.
    Ответы хранятся: повторное обучение не нагружает оператора. Без права history — пусто.
    """
    stored = repository.observations(session, [(r.application_id, r.as_of) for r in requests])
    result = {key: NetworkObservation.model_validate(value) for key, value in stored.items()}
    # по времени: пакет оператора читает события за окно от первого до последнего момента пакета
    pending = sorted((r for r in requests if (r.application_id, r.as_of) not in result), key=lambda r: r.as_of)
    client = ctx.history
    if not pending or client is None:
        return result
    items = sorted({item for r in pending for item in application_identifiers(r.snapshot)})
    tokens = tokenize(session, ctx, client, None, items, now)  # токены не зависят от контура
    by_realm: dict[UUID | None, list[CounterQuery]] = defaultdict(list)
    for r in pending:
        refs = [tokens[i] for i in application_identifiers(r.snapshot)]
        ref = f"{r.application_id}|{r.as_of.isoformat()}"
        by_realm[r.sandbox].append(CounterQuery(ref=ref, subject=refs[0], tokens=refs[1:], as_of=r.as_of))
    answers = {answer.ref: answer for sandbox, queries in by_realm.items() for answer in client.query(sandbox, queries)}
    rows = []
    for r in pending:
        answer = answers[f"{r.application_id}|{r.as_of.isoformat()}"]
        observation = NetworkObservation(
            status="ok", as_of=answer.as_of, counters=answer.counters, confirmed=answer.confirmed
        )
        result[(r.application_id, r.as_of)] = observation
        rows.append(
            {
                "application_id": r.application_id,
                "as_of": r.as_of,
                "contract": CONTRACT_VERSION,
                "observation": observation.model_dump(mode="json"),
                "created_at": now,
            }
        )
    repository.save_observations(session, rows)
    return result


def overview(
    session: Session, ctx: NetworkContext, realm: RealmContext, policy: Policy, decisions: dict[str, int]
) -> dict[str, Any]:
    stats: dict[str, Any] | None = None
    if ctx.client is not None:
        try:
            stats = ctx.client.stats(operator_realm(realm))
        except AppError:
            stats = None
    rules = policy.network
    return {
        "enabled": enabled(policy),
        "policy_version": policy.version,
        "contract": CONTRACT_VERSION,
        "configured": ctx.client is not None,
        "available": stats is not None,
        "toggle_path": TOGGLE_PATH,
        "rules": [r.model_dump() for r in rules.rules] if rules is not None else [],
        "operator": stats,
        "decisions": decisions,
        "notifications": repository.notifications_count(session, realm.id),
    }
