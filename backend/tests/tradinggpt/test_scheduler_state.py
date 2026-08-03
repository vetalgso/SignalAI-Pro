from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.tradinggpt.scheduler.state_repository import (
    SchedulerStateRepository,
)
from app.tradinggpt.scheduler.state_service import (
    SchedulerStateService,
)


def build_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_default_state_is_disabled() -> None:
    with build_session() as session:
        service = SchedulerStateService(
            SchedulerStateRepository(session)
        )

        state = service.get()

        assert state["enabled"] is False
        assert state["interval_seconds"] == 300
        assert state["next_run_at"] is None
        assert state[
            "consecutive_failures"
        ] == 0


def test_state_is_singleton() -> None:
    with build_session() as session:
        repository = SchedulerStateRepository(
            session
        )

        first = repository.get_or_create()
        second = repository.get_or_create()

        assert first.id == 1
        assert second.id == 1


def test_enable_calculates_next_run() -> None:
    with build_session() as session:
        service = SchedulerStateService(
            SchedulerStateRepository(session)
        )

        state = service.update(
            enabled=True,
            interval_seconds=120,
        )

        assert state["enabled"] is True
        assert state["interval_seconds"] == 120
        assert state["next_run_at"] is not None


def test_disable_clears_next_run() -> None:
    with build_session() as session:
        service = SchedulerStateService(
            SchedulerStateRepository(session)
        )

        service.update(
            enabled=True,
            interval_seconds=120,
        )
        state = service.update(
            enabled=False,
            interval_seconds=None,
        )

        assert state["enabled"] is False
        assert state["next_run_at"] is None


def test_interval_below_minimum_is_rejected() -> None:
    with build_session() as session:
        repository = SchedulerStateRepository(
            session
        )

        try:
            repository.update(
                interval_seconds=59
            )
        except ValueError as exc:
            assert "at least 60 seconds" in str(
                exc
            )
        else:
            raise AssertionError(
                "Unsafe scheduler interval accepted."
            )


def test_successful_cycle_resets_failures() -> None:
    with build_session() as session:
        repository = SchedulerStateRepository(
            session
        )

        repository.record_cycle(
            cycle_id=1,
            cycle_status="FAILED",
            finished_at=datetime.now(
                timezone.utc
            ),
        )
        state = repository.record_cycle(
            cycle_id=2,
            cycle_status="COMPLETED",
            finished_at=datetime.now(
                timezone.utc
            ),
        )

        assert state.last_cycle_id == 2
        assert state.consecutive_failures == 0


def test_failed_cycles_increment_counter() -> None:
    with build_session() as session:
        repository = SchedulerStateRepository(
            session
        )

        repository.record_cycle(
            cycle_id=1,
            cycle_status="FAILED",
            finished_at=None,
        )
        state = repository.record_cycle(
            cycle_id=2,
            cycle_status="FAILED",
            finished_at=None,
        )

        assert state.consecutive_failures == 2
        assert state.last_cycle_id == 2
