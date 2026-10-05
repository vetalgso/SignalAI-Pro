import asyncio
import importlib.util
import json
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.signal_lifecycle_cycle import SignalLifecycleCycle
from app.tradinggpt.signals import background
from app.tradinggpt.signals.lifecycle_journal import LifecycleJournal, result_summary


def result(errors=None):
    return {"checked_signals": 2, "updated_signals": 1, "transition_count": 2,
            "price_updates": 2, "errors": errors or [], "changes": []}


@pytest.fixture
def factory():
    engine = create_engine("sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SignalLifecycleCycle.__table__.create(engine)
    with engine.begin() as db:
        db.execute(text("CREATE TABLE journal_probe (id INTEGER PRIMARY KEY)"))
    yield sessionmaker(bind=engine)
    engine.dispose()


def rows(factory):
    with factory() as db:
        return list(db.scalars(select(SignalLifecycleCycle).order_by(SignalLifecycleCycle.id)))


def test_begin_is_durable_and_new_cycles_do_not_reclassify_running_rows(factory):
    first = LifecycleJournal(factory, 60)
    first.begin()
    row = rows(factory)[0]
    assert row.status == "RUNNING"
    assert row.completed_at is None
    assert row.checked_signals is None
    assert row.error_count is None
    assert row.poll_interval_seconds == 60
    assert len(row.worker_id) == 36
    second = LifecycleJournal(factory, 60)
    second.begin()
    second.complete(result())
    recorded = rows(factory)
    assert [row.status for row in recorded] == ["RUNNING", "COMPLETED"]
    assert recorded[1].error_count == 0
    assert recorded[1].transition_count == 2
    assert recorded[1].duration_seconds >= 0
    assert recorded[1].completed_at is not None


def test_partial_result_has_only_bounded_error_codes(factory):
    journal = LifecycleJournal(factory, 60)
    journal.begin()
    journal.complete(result([
        {"symbol": "PRIVATE_SYMBOL", "error": "TimeoutError", "message": "PRIVATE_SECRET"},
        {"error": "TimeoutError"}, {"error": "MarketDataError"},
        {"error": "PRIVATE_EXCEPTION"}, "PRIVATE_PAYLOAD",
    ]))
    row = rows(factory)[0]
    assert row.status == "PARTIAL"
    assert row.error_count == 5
    assert row.error_counts == {"UPSTREAM_TIMEOUT": 2, "MARKET_DATA_ERROR": 1, "UNKNOWN_ERROR": 2}
    assert row.checked_signals == row.price_updates == 2
    assert "PRIVATE" not in json.dumps(row.error_counts)


@pytest.mark.parametrize("payload", [None, {}, {**result(), "checked_signals": -1},
    {**result(), "price_updates": True}, {**result(), "errors": "PRIVATE"}])
def test_invalid_result_is_not_reported_as_success(payload):
    summary = result_summary(payload)
    assert summary == {"status": "FAILED", "error_count": 1,
                       "error_counts": {"INVALID_CYCLE_RESULT": 1}}


@pytest.mark.parametrize("error_class, expected_status, expected_code", [
    (RuntimeError, "FAILED", "UNKNOWN_ERROR"),
    (asyncio.CancelledError, "CANCELLED", "CYCLE_CANCELLED"),
])
def test_tracker_failure_rolls_back_pending_changes_but_keeps_journal(
    factory, monkeypatch, error_class, expected_status, expected_code,
):
    class Tracker:
        def __init__(self, repository):
            self.db = repository.db

        async def refresh_all(self):
            assert rows(factory)[0].status == "RUNNING"
            self.db.execute(text("INSERT INTO journal_probe (id) VALUES (1)"))
            raise error_class("PRIVATE_EXCEPTION_MESSAGE")

    monkeypatch.setattr(background, "SessionLocal", factory)
    monkeypatch.setattr(background, "SignalLifecycleTracker", Tracker)
    with pytest.raises(error_class):
        asyncio.run(background.refresh_product_signals())
    row = rows(factory)[0]
    assert row.status == expected_status
    assert row.checked_signals is None  # Unreturned progress is not invented.
    assert row.error_counts == {expected_code: 1}
    with factory() as db:
        assert db.scalar(text("SELECT count(*) FROM journal_probe")) == 0


@pytest.mark.parametrize("failure_at", [1, 3])
def test_journal_database_failure_does_not_prevent_tracker_work(factory, monkeypatch, caplog, failure_at):
    calls = 0

    def flaky_factory():
        nonlocal calls
        calls += 1
        if calls == failure_at:
            raise OperationalError("PRIVATE_SQL", {}, Exception("PRIVATE_CREDENTIAL"))
        return factory()

    class Tracker:
        def __init__(self, repository):
            self.db = repository.db

        async def refresh_all(self):
            self.db.execute(text("INSERT INTO journal_probe (id) VALUES (1)"))
            self.db.commit()
            return result()

    monkeypatch.setattr(background, "SessionLocal", flaky_factory)
    monkeypatch.setattr(background, "SignalLifecycleTracker", Tracker)
    assert asyncio.run(background.refresh_product_signals()) == result()
    with factory() as db:
        assert db.scalar(text("SELECT count(*) FROM journal_probe")) == 1
    assert "PRIVATE" not in caplog.text
    assert "JOURNAL_WRITE_FAILED" in caplog.text
    assert [row.status for row in rows(factory)] == ([] if failure_at == 1 else ["RUNNING"])


def test_background_exception_log_does_not_include_raw_message(monkeypatch, caplog):
    async def run():
        loop = background.SignalLifecycleBackgroundLoop(60)
        loop._stop_event = asyncio.Event()

        async def fail():
            loop._stop_event.set()
            raise RuntimeError("PRIVATE_EXCEPTION_MESSAGE")

        monkeypatch.setattr(background, "refresh_product_signals", fail)
        await loop._run()

    asyncio.run(run())
    assert "UNKNOWN_ERROR" in caplog.text
    assert "PRIVATE" not in caplog.text


def test_lifecycle_migration_upgrade_and_downgrade():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/20260909_0021_add_signal_lifecycle_cycles.py"
    spec = importlib.util.spec_from_file_location("lifecycle_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "20260903_0020"
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        columns = {column["name"] for column in inspect(connection).get_columns("signal_lifecycle_cycles")}
        assert columns == set(SignalLifecycleCycle.__table__.columns.keys())
        assert len(inspect(connection).get_indexes("signal_lifecycle_cycles")) == 2
        migration.downgrade()
        assert "signal_lifecycle_cycles" not in inspect(connection).get_table_names()
    engine.dispose()
