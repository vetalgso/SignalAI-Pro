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
                                limit=kwargs.get("limit", 25), offset=kwargs.get("offset", 0), now=NOW)


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
        for query in ("days=0", "days=366", "source=INVALID", "limit=101", "offset=-1"):
            assert client.get("/signals/quality?" + query).status_code == 422
    assert db.query(TradingSignal).count() == 1
    assert db.query(TradingSignalEvent).count() == 0
