"""Recovery tests use real DB transactions/events/outbox and offline candle pages."""
import asyncio
import importlib.util
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.trading_signal import TradingSignal, TradingSignalEvent, TelegramSignalDelivery
from app.tradinggpt.signals import lifecycle
from app.tradinggpt.signals.history import MINUTE
from app.tradinggpt.signals.lifecycle_journal import result_summary
from app.tradinggpt.signals.repository import TradingSignalRepository
from app.tradinggpt.signals.schemas import SignalCreateRequest, SignalResponse, SignalTransitionRequest
from app.tradinggpt.signals.service import TradingSignalService

BASE = datetime(2026, 9, 17, tzinfo=timezone.utc)


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool)
    for model in (TradingSignal, TradingSignalEvent, TelegramSignalDelivery):
        model.__table__.create(engine)
    with sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)() as session:
        yield session
    engine.dispose()


def create_signal(db, **overrides):
    request = SignalCreateRequest(**{
        "exchange": "BINANCE", "market_type": "SPOT", "symbol": "BTCUSDT",
        "timeframe": "1H", "side": "LONG", "strategy": "HISTORY_TEST",
        "source": "SCANNER", "confidence": "70", "risk_level": "MEDIUM",
        "entry_min": "99", "entry_max": "101", "stop_loss": "95",
        "take_profit_1": "105", "take_profit_2": "110", "take_profit_3": "115",
        "current_price": "100", "reasons": [], "generated_at": BASE,
        "expires_at": BASE + timedelta(days=30), **overrides,
    })
    return TradingSignalService(TradingSignalRepository(db)).create(request)


def raw_candle(at, *, high="103", low="102", close="102"):
    return {"open_time": int(at.timestamp() * 1000),
            "close_time": int((at + MINUTE).timestamp() * 1000) - 1,
            "high": high, "low": low, "close": close}


class History:
    def __init__(self, edits=None, transform=None):
        self.edits = edits or {}
        self.transform = transform or (lambda page: page)
        self.calls = []

    async def get_candle_history(self, **query):
        self.calls.append(query)
        page = [raw_candle(query["start_at"] + n * MINUTE,
                           **self.edits.get(query["start_at"] + n * MINUTE, {}))
                for n in range(query["limit"])]
        return self.transform(page)


def run(db, monkeypatch, history, now, tracker=None):
    monkeypatch.setattr(lifecycle, "utc_now", lambda: now)
    tracker = tracker or lifecycle.SignalLifecycleTracker(TradingSignalRepository(db), history)
    return asyncio.run(tracker.refresh_all())


def events(db, signal_id):
    return list(db.scalars(select(TradingSignalEvent).where(
        TradingSignalEvent.signal_id == signal_id,
    ).order_by(TradingSignalEvent.id)))


def test_old_stop_is_found_before_later_target_after_long_outage(db, monkeypatch):
    signal = create_signal(db)
    history = History({
        BASE: {"high": "101", "low": "99", "close": "100"},
        BASE + 10 * MINUTE: {"high": "100", "low": "94", "close": "96"},
        BASE + 500 * MINUTE: {"high": "116", "low": "110", "close": "115"},
    })
    # A price check must not skip the old entry and stop.
    TradingSignalService(TradingSignalRepository(db)).update_market_price(
        signal_id=signal.id, price=Decimal("115"), checked_at=BASE + 590 * MINUTE,
    )
    result = run(db, monkeypatch, history, BASE + 600 * MINUTE)
    assert result["errors"] == []
    assert [e.to_status for e in events(db, signal.id)] == ["ACTIVE", "ENTRY_REACHED", "STOPPED"]
    db.refresh(signal)
    assert signal.status == "STOPPED"
    assert lifecycle.aware_datetime(signal.lifecycle_next_candle_at) == BASE + 11 * MINUTE
    assert events(db, signal.id)[-1].payload["candle"]["opened_at"] == (BASE + 10 * MINUTE).isoformat()
    assert events(db, signal.id)[-1].payload["history"]["policy"] == "CLOSED_1M_V1"
    assert history.calls[0]["start_at"] == BASE


def test_backfill_resumes_from_durable_page_cursor_and_is_not_a_success_cycle(db, monkeypatch):
    signal = create_signal(db)
    history = History()
    first = run(db, monkeypatch, history, BASE + 1100 * MINUTE)
    assert result_summary(first)["error_counts"] == {"HISTORY_BACKFILL_PENDING": 1}
    assert result_summary(first)["status"] == "PARTIAL"
    db.refresh(signal)
    assert signal.lifecycle_history_status == "BACKFILL"
    assert lifecycle.aware_datetime(signal.lifecycle_next_candle_at) == BASE + 1000 * MINUTE
    # A new tracker instance resumes like a restarted worker.
    second = run(db, monkeypatch, history, BASE + 1100 * MINUTE)
    assert second["errors"] == []
    assert history.calls[-1]["start_at"] == BASE + 1000 * MINUTE
    assert history.calls[-1]["limit"] == 100
    db.refresh(signal)
    assert signal.lifecycle_history_status == "CURRENT"
    assert len(events(db, signal.id)) == 1
    third = run(db, monkeypatch, history, BASE + 1100 * MINUTE)
    assert third["transition_count"] == 0 and len(history.calls) == 2


@pytest.mark.parametrize("transform", [
    lambda page: [], lambda page: page[1:], lambda page: page[:-1],
    lambda page: [page[0], page[0]], lambda page: list(reversed(page)),
    lambda page: [{**page[0], "high": "NaN"}, page[1]],
    lambda page: [{**page[0], "low": "200"}, page[1]],
    lambda page: [{**page[0], "close": "999"}, page[1]],
    lambda page: [{**page[0], "close_time": page[0]["close_time"] + 1}, page[1]],
    lambda page: [{**x, "open_time": x["open_time"] + 60000} for x in page],
])
def test_bad_history_never_advances_or_expires_signal(db, monkeypatch, transform):
    signal = create_signal(db, expires_at=BASE + timedelta(seconds=90))
    result = run(db, monkeypatch, History(transform=transform), BASE + 2 * MINUTE)
    assert result_summary(result)["error_counts"] == {"HISTORY_GAP": 1}
    db.refresh(signal)
    assert signal.status == "ACTIVE" and signal.lifecycle_history_status == "GAP"
    assert lifecycle.aware_datetime(signal.lifecycle_next_candle_at) == BASE
    assert len(events(db, signal.id)) == 1
    assert db.scalar(select(func.count()).select_from(TelegramSignalDelivery)) == 1


def test_http_failure_is_retryable_without_latest_price_fallback(db, monkeypatch):
    signal = create_signal(db)
    class Offline:
        async def get_candle_history(self, **query):
            raise TimeoutError("PRIVATE_ERROR")
    result = run(db, monkeypatch, Offline(), BASE + 2 * MINUTE)
    assert result_summary(result)["error_counts"] == {"UPSTREAM_TIMEOUT": 1}
    db.refresh(signal)
    assert signal.lifecycle_history_status == "GAP"
    assert lifecycle.aware_datetime(signal.lifecycle_next_candle_at) == BASE
    result = run(db, monkeypatch, History(), BASE + 2 * MINUTE)
    assert result["errors"] == []
    db.refresh(signal)
    assert signal.lifecycle_history_status == "CURRENT"


def test_unclosed_minute_and_pre_creation_range_are_never_replayed(db, monkeypatch):
    signal = create_signal(db, generated_at=BASE + timedelta(seconds=30))
    history = History({BASE + MINUTE: {"high": "101", "low": "99", "close": "100"}})
    run(db, monkeypatch, history, BASE + MINUTE + timedelta(seconds=59))
    assert history.calls == []
    result = run(db, monkeypatch, history, BASE + 2 * MINUTE)
    assert history.calls[0]["start_at"] == BASE + MINUTE
    assert result["transition_count"] == 1
    assert events(db, signal.id)[-1].to_status == "ENTRY_REACHED"


def test_complete_entry_window_can_expire_but_ambiguous_boundary_cannot(db, monkeypatch):
    signal = create_signal(db, expires_at=BASE + timedelta(seconds=90))
    result = run(db, monkeypatch, History(), BASE + 2 * MINUTE)
    assert result["errors"] == []
    db.refresh(signal)
    assert signal.status == "EXPIRED"
    another = create_signal(db, symbol="ETHUSDT", expires_at=BASE + timedelta(seconds=90))
    boundary = History({BASE + MINUTE: {"high": "101", "low": "99", "close": "100"}})
    result = run(db, monkeypatch, boundary, BASE + 2 * MINUTE)
    assert result_summary(result)["error_counts"] == {"HISTORY_BOUNDARY_AMBIGUOUS": 1}
    db.refresh(another)
    assert another.status == "ACTIVE"
    assert len(events(db, another.id)) == 1


def test_legacy_and_manual_history_require_explicit_reconciliation(db, monkeypatch):
    signal = create_signal(db)
    signal.lifecycle_next_candle_at = None
    signal.lifecycle_history_status = "UNVERIFIED"
    db.commit()
    history = History()
    result = run(db, monkeypatch, history, BASE + 10 * MINUTE)
    assert result_summary(result)["error_counts"] == {"HISTORY_UNVERIFIED": 1}
    assert history.calls == []
    manual = create_signal(db, symbol="ETHUSDT")
    TradingSignalService(TradingSignalRepository(db)).transition(
        signal_id=manual.id, request=SignalTransitionRequest(status="ENTRY_REACHED", price="100"),
    )
    assert manual.lifecycle_history_status == "UNVERIFIED"
    assert manual.lifecycle_next_candle_at is None
    assert SignalResponse.model_validate(manual).lifecycle_history_status == "UNVERIFIED"


def test_futures_are_not_processed_with_spot_candles(db, monkeypatch):
    signal = create_signal(db, market_type="FUTURES")
    history = History()
    result = run(db, monkeypatch, history, BASE + 10 * MINUTE)
    assert result_summary(result)["error_counts"] == {"HISTORY_UNSUPPORTED_MARKET": 1}
    assert history.calls == []
    db.refresh(signal)
    assert signal.lifecycle_history_status == "UNSUPPORTED"


def test_failed_outbox_write_rolls_back_transitions_and_cursor_then_retries(db, monkeypatch):
    signal = create_signal(db)
    history = History({BASE: {"high": "116", "low": "99", "close": "115"}})
    tracker = lifecycle.SignalLifecycleTracker(TradingSignalRepository(db), history)
    enqueue = tracker.repository.enqueue_telegram_delivery
    calls = []
    def fail_second(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise RuntimeError("Injected outbox failure")
        return enqueue(*args, **kwargs)
    monkeypatch.setattr(tracker.repository, "enqueue_telegram_delivery", fail_second)
    result = run(db, monkeypatch, history, BASE + MINUTE, tracker)
    assert result["transition_count"] == 0 and len(result["errors"]) == 1
    db.refresh(signal)
    assert signal.status == "ACTIVE"
    assert lifecycle.aware_datetime(signal.lifecycle_next_candle_at) == BASE
    assert len(events(db, signal.id)) == 1
    assert db.scalar(select(func.count()).select_from(TelegramSignalDelivery)) == 1
    monkeypatch.setattr(tracker.repository, "enqueue_telegram_delivery", enqueue)
    result = run(db, monkeypatch, history, BASE + MINUTE, tracker)
    assert result["transition_count"] == 4
    assert [e.to_status for e in events(db, signal.id)] == [
        "ACTIVE", "ENTRY_REACHED", "TP1_REACHED", "TP2_REACHED", "TP3_REACHED",
    ]
    assert db.scalar(select(func.count()).select_from(TelegramSignalDelivery)) == 5
    again = run(db, monkeypatch, history, BASE + MINUTE, tracker)
    assert again["transition_count"] == 0
    assert len(events(db, signal.id)) == 5


def test_manual_change_during_fetch_discards_stale_history_page(db, monkeypatch):
    signal = create_signal(db)
    def manual_change(page):
        TradingSignalService(TradingSignalRepository(db)).transition(
            signal_id=signal.id, request=SignalTransitionRequest(status="CANCELLED"),
        )
        return page
    history = History(transform=manual_change)
    result = run(db, monkeypatch, history, BASE + MINUTE)
    assert result["transition_count"] == 0
    db.refresh(signal)
    assert signal.status == "CANCELLED" and signal.lifecycle_next_candle_at is None
    assert len(events(db, signal.id)) == 2


def test_migration_preserves_legacy_signals_and_events():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/20260917_0022_add_signal_history_cursor.py"
    spec = importlib.util.spec_from_file_location("history_cursor_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "20260909_0021"
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE trading_signals (id INTEGER PRIMARY KEY, status TEXT)"))
        connection.execute(text("INSERT INTO trading_signals VALUES (1, 'STOPPED'), (2, 'ACTIVE')"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert connection.execute(text(
            "SELECT status, lifecycle_next_candle_at, lifecycle_history_status FROM trading_signals ORDER BY id"
        )).all() == [("STOPPED", None, "UNVERIFIED"), ("ACTIVE", None, "UNVERIFIED")]
        migration.downgrade()
        assert [c["name"] for c in inspect(connection).get_columns("trading_signals")] == ["id", "status"]
        assert connection.execute(text("SELECT * FROM trading_signals ORDER BY id")).all() == [(1, "STOPPED"), (2, "ACTIVE")]
    engine.dispose()


def test_two_postgres_workers_commit_a_candle_only_once(monkeypatch):
    """CI uses real PostgreSQL row locks, not SQLite's ignored FOR UPDATE."""
    import os
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from uuid import uuid4

    url = os.environ.get("SIGNALAI_HISTORY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires isolated PostgreSQL test database; enabled in CI")
    schema = "history_test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, execution_options={"schema_translate_map": {None: schema}})
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        for model in (TradingSignal, TradingSignalEvent, TelegramSignalDelivery):
            model.__table__.create(engine)
        with factory() as db:
            signal_id = create_signal(db).id
        barrier = Barrier(2)
        def rendezvous(page):
            barrier.wait(timeout=10)
            return page
        monkeypatch.setattr(lifecycle, "utc_now", lambda: BASE + MINUTE)
        def worker():
            history = History({BASE: {"high": "116", "low": "99", "close": "115"}}, rendezvous)
            with factory() as db:
                tracker = lifecycle.SignalLifecycleTracker(TradingSignalRepository(db), history)
                return asyncio.run(tracker.refresh_all())
        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(worker) for _ in range(2)]
            results = [f.result(timeout=20) for f in futures]
        assert sum(r["transition_count"] for r in results) == 4
        assert all(not r["errors"] for r in results)
        with factory() as db:
            assert len(events(db, signal_id)) == 5
            assert db.scalar(select(func.count()).select_from(TelegramSignalDelivery)) == 5
            signal = db.get(TradingSignal, signal_id)
            assert signal.status == "TP3_REACHED"
            assert signal.lifecycle_next_candle_at == BASE + MINUTE
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_expiry_waits_for_backfill_and_finds_entry_in_the_missing_window(db, monkeypatch):
    signal = create_signal(db, expires_at=BASE + 1100 * MINUTE)
    history = History({BASE + 1050 * MINUTE: {"high": "101", "low": "99", "close": "100"}})
    first = run(db, monkeypatch, history, BASE + 1200 * MINUTE)
    assert first["transition_count"] == 0
    db.refresh(signal)
    assert signal.status == "ACTIVE" and signal.lifecycle_history_status == "BACKFILL"
    second = run(db, monkeypatch, history, BASE + 1200 * MINUTE)
    assert second["errors"] == []
    db.refresh(signal)
    assert signal.status == "ENTRY_REACHED"
    assert [e.to_status for e in events(db, signal.id)] == ["ACTIVE", "ENTRY_REACHED"]


def test_short_signal_recovers_earlier_stop_instead_of_later_profit(db, monkeypatch):
    signal = create_signal(db, side="SHORT", stop_loss="105", take_profit_1="95",
                           take_profit_2="90", take_profit_3="85")
    history = History({
        BASE: {"high": "101", "low": "99", "close": "100"},
        BASE + 10 * MINUTE: {"high": "106", "low": "100", "close": "104"},
        BASE + 500 * MINUTE: {"high": "90", "low": "84", "close": "85"},
    })
    result = run(db, monkeypatch, history, BASE + 600 * MINUTE)
    assert result["errors"] == []
    assert [e.to_status for e in events(db, signal.id)] == ["ACTIVE", "ENTRY_REACHED", "STOPPED"]
    assert events(db, signal.id)[-1].price == Decimal("105")


def test_entry_window_shorter_than_first_full_minute_is_not_invented(db, monkeypatch):
    signal = create_signal(db, generated_at=BASE + timedelta(seconds=10),
                           expires_at=BASE + timedelta(seconds=30))
    history = History()
    result = run(db, monkeypatch, history, BASE + MINUTE)
    assert result_summary(result)["error_counts"] == {"HISTORY_BOUNDARY_AMBIGUOUS": 1}
    assert history.calls == []
    db.refresh(signal)
    assert signal.status == "ACTIVE" and signal.lifecycle_history_status == "GAP"
