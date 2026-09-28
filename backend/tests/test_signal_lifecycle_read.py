from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.session import get_db
from app.models.signal_lifecycle_cycle import SignalLifecycleCycle
from app.tradinggpt.signals.lifecycle_read import read_lifecycle_state


NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SignalLifecycleCycle.__table__.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def cycle(db, *, age=20, status="COMPLETED", errors=0):
    item = SignalLifecycleCycle(
        worker_id="private-worker", status=status, started_at=NOW - timedelta(seconds=age + 1),
        completed_at=None if status == "RUNNING" else NOW - timedelta(seconds=age),
        duration_seconds=.312, poll_interval_seconds=60,
        error_count=errors, checked_signals=0, error_counts={"private exception": 1},
    )
    db.add(item)
    db.commit()
    return item


def read(db, enabled=True, interval=60):
    return read_lifecycle_state(db, enabled=enabled, interval_seconds=interval, now=NOW)


def test_empty_and_running_are_not_healthy(db):
    assert read(db).state == "WAITING"
    cycle(db, status="RUNNING")
    result = read(db)
    assert result.state == "WAITING"
    assert result.completed_at is None
    assert result.error_count is None
    assert read(db, False).state == "DISABLED"


def test_healthy_zero_signals_is_a_completed_check(db):
    cycle(db)
    result = read(db)
    assert result.state == "OK"
    assert result.checked_signals == 0
    assert result.error_count == 0
    assert result.age_seconds == 20
    assert result.duration_seconds == .312
    assert result.completed_at == NOW - timedelta(seconds=20)
    assert result.as_of == NOW


@pytest.mark.parametrize("status,errors", [("PARTIAL", 1), ("FAILED", 1), ("CANCELLED", 1), ("COMPLETED", 2)])
def test_failure_states_and_counts_are_visible(db, status, errors):
    cycle(db, status=status, errors=errors)
    result = read(db)
    assert result.state == "ERRORS"
    assert result.error_count == errors
    assert result.cycle_status == status
    assert "private" not in result.model_dump_json()


def test_stale_threshold_and_disabled_history(db):
    item = cycle(db, age=180, status="FAILED", errors=1)
    assert read(db).state == "ERRORS"
    item.completed_at -= timedelta(seconds=1)
    db.commit()
    assert read(db).state == "STALE"
    assert read(db, interval=120).state == "ERRORS"
    result = read(db, False)
    assert result.state == "DISABLED"
    assert result.error_count == 1
    assert result.completed_at is not None


def test_order_by_completion_and_ignore_running(db):
    cycle(db, age=20, errors=2)
    cycle(db, age=100, errors=0)
    cycle(db, status="RUNNING")
    assert read(db).state == "ERRORS"
    assert read(db).age_seconds == 20


def test_missing_counts_not_zero_and_future_time_clamped(db):
    item = cycle(db, age=-10, errors=None)
    item.checked_signals = None
    item.duration_seconds = None
    db.commit()
    result = read(db)
    assert result.state == "UNKNOWN"
    assert result.age_seconds == 0
    assert result.error_count is result.checked_signals is result.duration_seconds is None


def test_route_is_json_read_only_and_does_not_match_signal_id(db, monkeypatch):
    from types import SimpleNamespace
    from app.tradinggpt.signals import lifecycle_read
    from app.tradinggpt.signals.router import router

    cycle(db)
    monkeypatch.setattr(lifecycle_read, "settings", SimpleNamespace(
        signal_tracking_enabled=False, signal_tracking_interval_seconds=90,
    ))
    app = FastAPI()
    app.include_router(router, prefix="/api/v3")
    app.dependency_overrides[get_db] = lambda: db
    statements = []
    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(db.bind, "before_cursor_execute", record)
    try:
        with TestClient(app) as client:
            response = client.get("/api/v3/signals/runtime/lifecycle")
        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "DISABLED"
        assert data["poll_interval_seconds"] == 90
        assert data["stale_after_seconds"] == 270
        assert set(data) == {
            "as_of", "enabled", "poll_interval_seconds", "stale_after_seconds", "state",
            "completed_at", "age_seconds", "duration_seconds", "error_count",
            "checked_signals", "cycle_status",
        }
        assert "private" not in response.text
        assert len(statements) == 1
        assert statements[0].lstrip().upper().startswith("SELECT")
    finally:
        event.remove(db.bind, "before_cursor_execute", record)
