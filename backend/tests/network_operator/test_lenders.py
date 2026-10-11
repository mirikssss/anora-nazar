"""Кредиторы Б и В имитатора банка: прогон истории мира в общий мир оператора — point-in-time по времени мира,
результаты дел только с идентификаторами мошенника, повтор безопасен."""

from datetime import timedelta
from types import SimpleNamespace
from typing import Any

from bank_sim.modules.lenders import service as lenders
from bank_sim.network_gateway import NetworkGateway
from bank_sim.settings import LendersConfig
from shared.contracts.network import CounterQuery
from tests.network_operator.conftest import KEYS, START, Operator
from world.records import OtherLenderApplication, OtherLenderConfirmation, OtherLenderTransfer

CARD = "8600123412341234"
CONFIG = LendersConfig(delivery_delay_seconds=60, history_chunk=1, timeout_seconds=5)


def _record(number: int, lender: str, pinfl: str, **extra: Any) -> OtherLenderApplication:
    moment = START - timedelta(days=10 - number)
    values: dict[str, Any] = {
        "id": f"W{lender}-{number:06d}",
        "lender": lender,
        "channel": "online",
        "pinfl": pinfl,
        "phone": f"99890000000{number}",
        "device_id": None,
        "amount": 5_000_000,
        "occurred_at": moment,
        "supplier_inn": None,
        "issued_at": moment + timedelta(hours=1),
        "transfer": OtherLenderTransfer(card=CARD, credit_share=0.9, occurred_at=moment + timedelta(hours=2)),
        "confirmation": None,
    }
    return OtherLenderApplication(**(values | extra))


def test_world_history_reaches_operator_point_in_time(operator: Operator) -> None:
    env = SimpleNamespace(
        network_key_b=KEYS["OPERATOR_API_KEY_B"],
        network_key_c=KEYS["OPERATOR_API_KEY_C"],
        network_key_b_history=KEYS["OPERATOR_API_KEY_B_HISTORY"],
        network_key_c_history=KEYS["OPERATOR_API_KEY_C_HISTORY"],
        network_key_admin=KEYS["OPERATOR_API_KEY_BANK_SIM"],
    )
    gateway = NetworkGateway(env, "http://operator", 5, operator.transport())  # type: ignore[arg-type]
    fraud = OtherLenderConfirmation(
        typology="F1", confirmation="confirmed_coercion", confirmed_at=START - timedelta(days=2), kinds=["card"]
    )
    world = SimpleNamespace(
        other_lenders=[_record(1, "B", "31111111111111", confirmation=fraud), _record(2, "C", "32222222222222")]
    )
    first = lenders.replay_history(gateway, world, CONFIG, lambda *_: None)  # type: ignore[arg-type]
    assert first["B"]["accepted"] == 3 and first["B"]["results"] == 1
    again = lenders.replay_history(gateway, world, CONFIG, lambda *_: None)  # type: ignore[arg-type]
    assert again["C"]["duplicates"] == 3 and again["C"]["accepted"] == 0

    history = operator.lender("OPERATOR_API_KEY_A_HISTORY")
    refs = history.tokenize(None, [("pinfl", "30000000000000"), ("card", CARD)])
    query = CounterQuery(ref="A-1", subject=refs[("pinfl", "30000000000000")], tokens=[refs[("card", CARD)]])

    def at(moment: Any) -> Any:
        return history.query(None, [query.model_copy(update={"as_of": moment})])[0]

    early, later, now = at(START - timedelta(days=8)), at(START - timedelta(days=7)), at(START)
    assert early.counters["card_borrowers_30d"] == 1 and not early.confirmed  # перевод Б уже получен, В — ещё нет
    assert later.counters["card_borrowers_30d"] == 2 and later.counters["card_lenders_30d"] == 2
    assert [(m.kind, m.confirmation) for m in now.confirmed] == [("card", "confirmed_coercion")]
