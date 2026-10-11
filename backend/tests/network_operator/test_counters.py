"""Чистая функция счётчиков: только чужие кредиторы, уникальные люди без заявителя, окна и point-in-time
с исправлением и отменой; совпадения с закрытыми делами."""

from datetime import UTC, datetime, timedelta

from network_operator.modules.activity.domain import EventVersion, Span, place_correction
from network_operator.modules.confirmed.domain import ConfirmedFact
from network_operator.modules.counters.domain import QueryTokens, confirmed_matches, counters
from network_operator.settings import PACKAGE_DIR, load_config

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)
WINDOWS = load_config(PACKAGE_DIR / "config" / "operator.yaml").counters.durations()
APPLICANT = "p0"
PINFL = ("pinfl", 1, APPLICANT)
PHONE = ("phone", 1, "phone-token")
QUERY = QueryTokens(requester="A", applicant=APPLICANT, tokens=[PINFL, PHONE], as_of=NOW)


def _app(
    lender: str, subject: str, ago: timedelta, *, received: timedelta | None = None, until: datetime | None = None
) -> EventVersion:
    return EventVersion(
        lender=lender,
        subject=subject,
        fact="application",
        occurred_at=NOW - ago,
        received_at=NOW - (ago if received is None else received),
        valid_until=until,
    )


def test_other_lenders_unique_people_and_windows() -> None:
    hour = timedelta(hours=1)
    versions = {
        PHONE: [
            _app("B", "p1", hour),
            _app("B", "p1", 2 * hour),  # тот же человек — повторная заявка
            _app("C", "p2", 3 * hour),
            _app("A", "p3", hour),  # свой кредитор — в своём индексе связей
            _app("B", APPLICANT, hour),  # сам заявитель
            _app("C", "p4", 25 * hour),  # вне суточного окна
        ],
        PINFL: [
            _app("B", APPLICANT, timedelta(minutes=30)),
            _app("C", APPLICANT, 50 * hour),
            _app("A", APPLICANT, hour),
        ],
    }
    result = counters(QUERY, versions, WINDOWS)
    assert result["phone_people_24h"] == 2
    assert result["phone_people_30d"] == 3
    assert result["pinfl_lenders_1h"] == 1
    assert result["pinfl_lenders_7d"] == 2
    assert result["device_people_30d"] == 0


def test_point_in_time_with_correction_and_retraction() -> None:
    day = timedelta(days=1)
    corrected_at, retracted_at = NOW - 2 * day, NOW - day
    versions = {
        PHONE: [
            _app("B", "p5", 5 * day, until=corrected_at),  # исправление убрало телефон
            _app("C", "p6", 5 * day, until=retracted_at),  # ошибочная запись отменена
            _app("C", "p7", 5 * day, received=timedelta(hours=1)),  # получено оператором только что
        ]
    }

    def people(as_of: datetime) -> int:
        query = QueryTokens(requester="A", applicant=APPLICANT, tokens=[PHONE], as_of=as_of)
        return counters(query, versions, WINDOWS)["phone_people_30d"]

    assert people(NOW - 3 * day) == 2
    assert people(NOW - timedelta(days=1.5)) == 1
    assert people(NOW - timedelta(hours=2)) == 0
    assert people(NOW) == 1


def test_correction_takes_effect_from_receipt_but_not_before_original() -> None:
    base, first = Span(1, NOW - timedelta(days=3), NOW - timedelta(days=1)), Span(2, NOW - timedelta(days=1), None)
    middle = place_correction([base, first], NOW - timedelta(days=2))
    assert (middle.cuts, middle.superseded_at) == (1, first.received_at)
    early = place_correction([base], NOW - timedelta(days=9))
    assert early.received_at == base.received_at


def test_confirmed_matches_only_from_others_and_before_as_of() -> None:
    hour = timedelta(hours=1)
    facts = {
        PHONE: [
            ConfirmedFact("C", "phone", "F2", "confirmed_fraud", NOW - hour, NOW - hour),
            ConfirmedFact("A", "phone", "F1", "confirmed_fraud", NOW - hour, NOW - hour),
            ConfirmedFact("B", "phone", "F1", "confirmed_coercion", NOW + hour, NOW + hour),
        ]
    }
    matches = confirmed_matches(QUERY, facts)
    assert [(m.kind, m.typology, m.confirmation) for m in matches] == [("phone", "F2", "confirmed_fraud")]
