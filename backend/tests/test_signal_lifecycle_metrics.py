from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.signal_lifecycle_cycle import SignalLifecycleCycle
from app.tradinggpt.signals.lifecycle_metrics import render_lifecycle_metrics


NOW = datetime(2026, 9, 9, 10, tzinfo=timezone.utc)
PREFIX = "signalai_signal_lifecycle_"


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    SignalLifecycleCycle.__table__.create(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def add_cycle(session, *, status="COMPLETED", age=10, duration=0.25, errors=0):
    cycle = SignalLifecycleCycle(
        worker_id="private-worker", status=status,
        started_at=NOW - timedelta(seconds=age + 1),
        completed_at=None if status == "RUNNING" else NOW - timedelta(seconds=age),
        duration_seconds=duration, poll_interval_seconds=60,
        error_count=errors, error_counts={"private-error": errors},
    )
    session.add(cycle)
    session.commit()
    return cycle


def render(session, enabled=True):
    lines = render_lifecycle_metrics(session, enabled=enabled, interval_seconds=60, now=NOW)
    text = "\n".join(lines)
    values = {line.split()[0]: float(line.split()[1]) for line in lines if not line.startswith("#")}
    assert "private" not in text
    assert "{" not in text
    assert all(line.endswith(" gauge") for line in lines if line.startswith("# TYPE"))
    return {name.removeprefix(PREFIX): value for name, value in values.items()}


def test_empty_journal_does_not_report_healthy_zero_age(session):
    assert render(session) == {"enabled": 1, "poll_interval_seconds": 60, "latest_completed_observed": 0}


def test_running_cycle_is_not_a_completion(session):
    add_cycle(session, status="RUNNING")
    assert render(session)["latest_completed_observed"] == 0
    assert "latest_errors" not in render(session)


@pytest.mark.parametrize("status", ["COMPLETED", "PARTIAL", "FAILED", "CANCELLED"])
def test_finished_statuses_export_latest_snapshot(session, status):
    add_cycle(session, status=status, errors=2)
    assert render(session) == {
        "enabled": 1, "poll_interval_seconds": 60, "latest_completed_observed": 1,
        "seconds_since_last_completion": 10, "latest_duration_seconds": .25, "latest_errors": 2,
    }


def test_completion_time_not_id_selects_latest_and_running_does_not_hide_it(session):
    add_cycle(session, age=5, errors=2)
    add_cycle(session, age=50, errors=0)
    add_cycle(session, status="RUNNING")
    assert render(session)["latest_errors"] == 2
    assert render(session)["seconds_since_last_completion"] == 5


def test_new_success_replaces_error_snapshot_and_disabled_keeps_history(session):
    add_cycle(session, status="FAILED", errors=2, age=50)
    add_cycle(session, errors=0, age=5)
    assert render(session, enabled=False)["enabled"] == 0
    assert render(session, enabled=False)["latest_errors"] == 0


def test_null_duration_and_errors_remain_unknown(session):
    add_cycle(session, duration=None, errors=None)
    values = render(session)
    assert values["latest_completed_observed"] == 1
    assert "latest_duration_seconds" not in values
    assert "latest_errors" not in values


def test_future_completion_age_is_clamped(session):
    add_cycle(session, age=-5)
    assert render(session)["seconds_since_last_completion"] == 0
