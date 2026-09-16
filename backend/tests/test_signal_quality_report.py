from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.models.trading_signal import TradingSignal, TradingSignalEvent
from app.tradinggpt.signals.quality_report import build_quality_report
from app.tradinggpt.signals.router import router

NOW = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def add_signal(db, number, status, events=(), *, source="AI_REVIEW",
               generated=None, market_type="SPOT", strategy="TEST", manual=False):
    signal = TradingSignal(
        fingerprint=f"test-{number}", exchange="BINANCE", market_type=market_type,
        symbol="BTCUSDT", timeframe="1H", side="LONG", strategy=strategy,
        status=status, confidence=70, risk_level="MEDIUM", risk_reward=1,
        entry_min=100, entry_max=100, stop_loss=99, take_profit_1=101,
        take_profit_2=None, take_profit_3=103,
        source=source, generated_at=generated or NOW - timedelta(days=1),
    )
    db.add(signal)
    db.flush()
    for index, target in enumerate(events):
        db.add(TradingSignalEvent(signal_id=signal.id,
            event_type="STATUS_CHANGED" if manual else "MARKET_STATUS_CHANGED",
            to_status=target, created_at=NOW - timedelta(minutes=10 - index)))
    db.commit()
    return signal


def report(db, **kwargs):
    return build_quality_report(db, days=30, source=kwargs.get("source", "AI_REVIEW"),
                                limit=kwargs.get("limit", 25), offset=kwargs.get("offset", 0), now=NOW,
                                transition_origin=kwargs.get("transition_origin", "ALL"))


def test_milestones_survive_stop_and_repeated_events_are_counted_once(db):
    add_signal(db, 1, "STOPPED", ("ENTRY_REACHED", "TP1_REACHED", "TP1_REACHED", "STOPPED"))
    add_signal(db, 2, "TP3_REACHED", ("ENTRY_REACHED", "TP1_REACHED", "TP3_REACHED"))
    result = report(db).summary
    assert result.total == result.terminal == result.entered == 2
    assert result.tp1 == 2
    assert result.tp2 == 0  # Optional target: never inferred from TP3.
    assert result.tp3 == result.stopped == 1
    assert result.open == 0


def test_scope_cohort_boundaries_pagination_and_missing_history(db):
    add_signal(db, 1, "ACTIVE", generated=NOW - timedelta(days=30))
    add_signal(db, 2, "EXPIRED", ("ACTIVE", "EXPIRED"))
    add_signal(db, 3, "CANCELLED", ("CANCELLED",), manual=True)
    add_signal(db, 4, "CUSTOM")
    add_signal(db, 5, "ACTIVE", market_type="FUTURES", strategy="OTHER")
    add_signal(db, 6, "ACTIVE", source="SCANNER")
    add_signal(db, 7, "ACTIVE", generated=NOW - timedelta(days=30, microseconds=1))
    add_signal(db, 8, "ACTIVE", generated=NOW + timedelta(microseconds=1))
    result = report(db, limit=1)
    assert result.summary.total == 5
    assert result.summary.open == 2
    assert result.summary.terminal == 2
    assert result.summary.unknown_status == 1
    assert result.summary.entered == result.summary.tp1 == 0
    assert result.summary.without_events == 3
    assert result.summary.manual_transitions == 1
    assert result.total_groups == 2
    assert len(result.groups) == 1
    other = report(db, limit=1, offset=1)
    assert result.groups[0].market_type != other.groups[0].market_type
    assert result.summary == other.summary
    assert report(db, offset=2).groups == []
    assert report(db, source="ALL").summary.total == 6
    assert report(db, source="SCANNER").summary.total == 1


def test_empty_cohort_and_entry_timestamp_fallback(db):
    assert report(db).summary.total == 0
    assert report(db).groups == []
    signal = add_signal(db, 1, "STOPPED")
    signal.entry_reached_at = NOW - timedelta(hours=1)
    db.commit()
    result = report(db).summary
    assert result.entered == result.without_events == 1
    assert result.tp1 == 0


def test_quality_route_validation_and_read_only_behavior(db):
    add_signal(db, 1, "ACTIVE", generated=datetime.now(timezone.utc) - timedelta(hours=1))
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        response = client.get("/signals/quality")
        assert response.status_code == 200
        assert response.json()["summary"]["total"] == 1
        assert response.json()["source"] == "AI_REVIEW"
        assert response.json()["transition_origin"] == "ALL"
        for query in ("days=0", "days=366", "source=INVALID", "limit=101", "offset=-1",
                      "transition_origin=INVALID", "transition_origin=automatic"):
            assert client.get("/signals/quality?" + query).status_code == 422
    assert db.query(TradingSignal).count() == 1
    assert db.query(TradingSignalEvent).count() == 0


def add_history(db, signal, event_types, *, created_at=NOW):
    for event_type in event_types:
        db.add(TradingSignalEvent(
            signal_id=signal.id, event_type=event_type,
            from_status=None if event_type == "CREATED" else "ACTIVE",
            to_status="ACTIVE" if event_type == "CREATED" else "ENTRY_REACHED",
            # Even this flag cannot establish origin without a known event type.
            payload={"automatic": True}, created_at=created_at,
        ))
    db.commit()


@pytest.mark.parametrize(("event_types", "expected"), [
    (["MARKET_STATUS_CHANGED"], "AUTOMATIC"),
    (["CREATED", "MARKET_STATUS_CHANGED"], "AUTOMATIC"),
    (["MARKET_STATUS_CHANGED"] * 3, "AUTOMATIC"),
    (["STATUS_CHANGED"], "MANUAL"),
    (["STATUS_CHANGED"] * 3, "MANUAL"),
    (["MARKET_STATUS_CHANGED", "STATUS_CHANGED"], "MANUAL"),
    (["STATUS_CHANGED", "MARKET_STATUS_CHANGED"], "MANUAL"),
    (["LEGACY_STATUS_CHANGED", "STATUS_CHANGED"], "MANUAL"),
    (["MARKET_STATUS_CHANGED", "LEGACY_STATUS_CHANGED", "STATUS_CHANGED"], "MANUAL"),
    (["LEGACY_STATUS_CHANGED"], "UNKNOWN"),
    (["MARKET_STATUS_CHANGED", "LEGACY_STATUS_CHANGED"], "UNKNOWN"),
    (["CREATED"], "UNKNOWN"),
    (["CREATED"] * 3, "UNKNOWN"),
    ([], "UNKNOWN"),
])
def test_transition_origin_partition_and_repeated_events(db, event_types, expected):
    signal = add_signal(db, 1, "ENTRY_REACHED")
    add_history(db, signal, event_types)
    # Current status / entry timestamp is not evidence of automatic provenance.
    signal.entry_reached_at = NOW - timedelta(minutes=1)
    db.commit()
    for origin in ("AUTOMATIC", "MANUAL", "UNKNOWN"):
        result = report(db, transition_origin=origin)
        assert result.transition_origin == origin
        assert result.summary.total == int(origin == expected)
        assert result.summary.entered == int(origin == expected)
        assert result.summary.manual_transitions == int(origin == expected == "MANUAL")
        assert result.total_groups == len(result.groups) == int(origin == expected)
    default = build_quality_report(db, days=30, source="AI_REVIEW", limit=25, offset=0, now=NOW)
    assert default == report(db, transition_origin="ALL")
    assert default.summary.total == 1
    assert db.query(TradingSignalEvent).count() == len(event_types)


@pytest.mark.parametrize(("past", "future", "expected"), [
    ([], ["MARKET_STATUS_CHANGED"], "UNKNOWN"),
    (["CREATED"], ["STATUS_CHANGED"], "UNKNOWN"),
    (["MARKET_STATUS_CHANGED"], ["STATUS_CHANGED"], "AUTOMATIC"),
    (["MARKET_STATUS_CHANGED"], ["LEGACY_STATUS_CHANGED"], "AUTOMATIC"),
    (["STATUS_CHANGED"], ["MARKET_STATUS_CHANGED"], "MANUAL"),
    (["LEGACY_STATUS_CHANGED"], ["MARKET_STATUS_CHANGED"], "UNKNOWN"),
])
def test_origin_uses_only_events_at_or_before_as_of(db, past, future, expected):
    signal = add_signal(db, 1, "ACTIVE")
    add_history(db, signal, past, created_at=NOW)
    add_history(db, signal, future, created_at=NOW + timedelta(microseconds=1))
    for origin in ("AUTOMATIC", "MANUAL", "UNKNOWN"):
        result = report(db, transition_origin=origin)
        assert result.summary.total == int(origin == expected)
    assert report(db).summary.without_events == int(not past)
    assert report(db).summary.entered == int(any(kind != "CREATED" for kind in past))


def test_origin_filters_before_summary_groups_and_pagination_with_existing_scope(db):
    # Each origin has two groups; a third automatic signal shares a group.
    for number, (origin, strategy) in enumerate([
        ("AUTOMATIC", "A"), ("AUTOMATIC", "B"), ("AUTOMATIC", "A"),
        ("MANUAL", "A"), ("MANUAL", "B"), ("UNKNOWN", "A"), ("UNKNOWN", "B"),
    ], start=1):
        signal = add_signal(db, number, "STOPPED", strategy=strategy)
        event_types = {
            "AUTOMATIC": ["MARKET_STATUS_CHANGED"] * 2,
            "MANUAL": ["MARKET_STATUS_CHANGED", "STATUS_CHANGED"],
            "UNKNOWN": ["MARKET_STATUS_CHANGED", "LEGACY_STATUS_CHANGED"],
        }[origin]
        add_history(db, signal, event_types)

    # Existing source and inclusive creation-window boundaries still apply.
    for number, generated, source in [
        (8, NOW - timedelta(days=30), "AI_REVIEW"),
        (9, NOW, "AI_REVIEW"),
        (10, NOW - timedelta(days=30, microseconds=1), "AI_REVIEW"),
        (11, NOW + timedelta(microseconds=1), "AI_REVIEW"),
        (12, NOW, "SCANNER"),
    ]:
        signal = add_signal(db, number, "ACTIVE", strategy="C", generated=generated, source=source)
        add_history(db, signal, ["MARKET_STATUS_CHANGED"])

    summaries = []
    for origin, total, group_count in [("AUTOMATIC", 5, 3), ("MANUAL", 2, 2), ("UNKNOWN", 2, 2)]:
        complete = report(db, transition_origin=origin)
        summaries.append(complete.summary)
        assert complete.summary.total == complete.summary.entered == total
        assert complete.summary.manual_transitions == (total if origin == "MANUAL" else 0)
        assert complete.summary.open == (2 if origin == "AUTOMATIC" else 0)
        assert complete.summary.stopped == complete.summary.terminal == total - complete.summary.open
        assert complete.total_groups == group_count
        assert sum(group.total for group in complete.groups) == total
        assert complete.groups[0].total == (2 if origin == "AUTOMATIC" else 1)
        for offset in range(group_count + 1):
            page = report(db, transition_origin=origin, limit=1, offset=offset)
            assert page.summary == complete.summary
            assert page.total_groups == group_count
            assert page.groups == complete.groups[offset:offset + 1]

    all_summary = report(db).summary
    for field in type(all_summary).model_fields:
        assert getattr(all_summary, field) == sum(getattr(summary, field) for summary in summaries)
    assert report(db, transition_origin="AUTOMATIC", source="ALL").summary.total == 6
    assert report(db, transition_origin="AUTOMATIC", source="SCANNER").summary.total == 1


def test_quality_api_origin_filter_and_read_only_history(db, monkeypatch):
    from app.tradinggpt.signals import quality_report

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(quality_report, "datetime", FixedDatetime)
    for number, event_types in enumerate([
        ["MARKET_STATUS_CHANGED"], ["STATUS_CHANGED"],
        ["MARKET_STATUS_CHANGED", "STATUS_CHANGED"], ["CREATED"], [],
    ], start=1):
        signal = add_signal(db, number, "ACTIVE", strategy=str(number))
        add_history(db, signal, event_types)
    app = FastAPI()
    app.include_router(router, prefix="/api/v3")
    app.dependency_overrides[get_db] = lambda: db
    tables = (TradingSignal.__table__, TradingSignalEvent.__table__)
    before = [db.execute(table.select()).all() for table in tables]
    with TestClient(app) as client:
        base = "/api/v3/signals/quality"
        assert client.get(base).json() == client.get(base + "?transition_origin=ALL").json()
        for origin, total in [("ALL", 5), ("AUTOMATIC", 1), ("MANUAL", 2), ("UNKNOWN", 2)]:
            response = client.get(base, params={"transition_origin": origin, "limit": 1, "offset": 1})
            assert response.status_code == 200
            body = response.json()
            assert body["transition_origin"] == origin
            assert body["summary"]["total"] == body["total_groups"] == total
            assert len(body["groups"]) == int(total > 1)
    assert [db.execute(table.select()).all() for table in tables] == before
