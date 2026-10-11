"""Оператор сети целиком: токен стабилен через общий клиент, контуры не видят друг друга, квота OPRF,
уведомление о новом совпадении уходит узлу, демо-сбой контура."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from shared.contracts.network import ActivityEvent, CounterQuery, TokenRef
from shared.errors import UpstreamUnavailableError
from shared.network.client import NetworkClient
from tests.network_operator.conftest import KEYS, START, Operator


def _application(
    lender: NetworkClient, realm: UUID | None, pinfl: str, phone: str, *, device: str | None = None
) -> ActivityEvent:
    items = [("pinfl", pinfl), ("phone", phone)] + ([("device", device)] if device else [])
    refs = lender.tokenize(realm, items)  # type: ignore[arg-type]
    return ActivityEvent(
        event_id=str(uuid4()),
        kind="application",
        occurred_at=START,
        channel="online",
        subject=refs[("pinfl", pinfl)],
        tokens=[refs[item] for item in items[1:]],  # type: ignore[index]
    )


def _query(lender: NetworkClient, realm: UUID | None, pinfl: str, phone: str, **extra: object) -> CounterQuery:
    refs = lender.tokenize(realm, [("pinfl", pinfl), ("phone", phone)])
    return CounterQuery(ref="APP-1", subject=refs[("pinfl", pinfl)], tokens=[refs[("phone", phone)]], **extra)  # type: ignore[arg-type]


def test_tokens_are_stable_and_realms_isolated(operator: Operator) -> None:
    a, b, c = (operator.lender(f"OPERATOR_API_KEY_{x}") for x in "ABC")
    first, second = uuid4(), uuid4()
    phone = "998901112233"
    once = a.tokenize(first, [("phone", phone)])[("phone", phone)]
    again = b.tokenize(None, [("phone", "+998 (90) 111-22-33")])[("phone", "+998 (90) 111-22-33")]
    assert once == again and isinstance(once, TokenRef)

    b.send_activity(first, [_application(b, first, "31111111111111", phone)])
    c.send_activity(None, [_application(c, None, "32222222222222", phone)])

    def people(realm: UUID | None) -> int:
        return a.query(realm, [_query(a, realm, "30000000000000", phone)])[0].counters["phone_people_24h"]

    assert (people(first), people(second), people(None)) == (2, 1, 1)
    assert operator.admin("DELETE", f"/v1/realms/{first}").status_code == 204
    assert people(first) == 1


def test_oprf_quota_follows_real_applications(operator: Operator) -> None:
    a, history = operator.lender("OPERATOR_API_KEY_A"), operator.lender("OPERATOR_API_KEY_A_HISTORY")
    realm = uuid4()
    reserve = operator.ctx.config.quotas.reserve
    phones = [f"99890{i:07d}" for i in range(reserve + 1)]
    a.tokenize(realm, [("phone", p) for p in phones[:reserve]])
    with pytest.raises(UpstreamUnavailableError) as error:
        a.tokenize(realm, [("phone", phones[reserve])])
    assert (error.value.code, error.value.status_code) == ("oprf_quota_exceeded", 429)

    history.tokenize(realm, [("phone", p) for p in phones])  # прогон истории квотой не ограничен
    b = operator.lender("OPERATOR_API_KEY_B")
    a.send_activity(realm, [_application(b, realm, "33333333333333", phones[0])])  # токены — чужими руками
    a.tokenize(realm, [("phone", phones[reserve])])


def test_new_match_notifies_watching_lender(operator: Operator) -> None:
    a, b = operator.lender("OPERATOR_API_KEY_A"), operator.lender("OPERATOR_API_KEY_B")
    realm = uuid4()
    phone, device = "998935556677", "dev-shared"
    watched = _query(a, realm, "34444444444444", phone, watch_until=operator.clock.now() + timedelta(hours=1))
    device_ref = a.tokenize(realm, [("device", device)])[("device", device)]
    a.query(realm, [watched.model_copy(update={"tokens": [*watched.tokens, device_ref]})])

    event = _application(b, realm, "35555555555555", phone, device=device)
    b.send_activity(realm, [event])
    assert b.send_activity(realm, [event]).duplicates == 1
    operator.tasks.deliver_notifications()

    assert len(operator.node.received) == 1
    sent = operator.node.received[0]
    assert sent["url"] == "http://node/v1/network/notifications"
    assert sent["authorization"] == f"Bearer {KEYS['OPERATOR_CALLBACK_KEY_A']}"
    assert sent["realm"] == str(realm)
    assert (sent["body"]["ref"], sent["body"]["kinds"]) == ("APP-1", ["device", "phone"])

    operator.tasks.deliver_notifications()
    assert len(operator.node.received) == 1  # доставленное не повторяется

    assert operator.admin("PUT", f"/v1/demo/realms/{realm}/outage", {"active": True}).status_code == 200
    with pytest.raises(UpstreamUnavailableError) as error:
        a.query(realm, [watched])
    assert error.value.code == "network_unavailable"
