from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.tradinggpt.scheduler.runner import (
    SafeSchedulerRunner,
)
from app.tradinggpt.scheduler.state_repository import (
    SchedulerStateRepository,
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


def test_disabled_runner_skips() -> None:
    with build_session() as session:
        repository = SchedulerStateRepository(
            session
        )
        calls = 0

        def callback():
            nonlocal calls
            calls += 1
            return {}

        runner = SafeSchedulerRunner(
            state_repository=repository,
            cycle_callback=callback,
        )

        result = runner.tick()

        assert result["action"] == (
            "SKIPPED_DISABLED"
        )
        assert calls == 0


def test_enabled_runner_without_payload_skips() -> None:
    with build_session() as session:
        repository = SchedulerStateRepository(
            session
        )
        repository.update(
            enabled=True,
            interval_seconds=60,
        )

        runner = SafeSchedulerRunner(
            state_repository=repository,
            cycle_callback=lambda: None,
        )

        result = runner.tick(force=True)

        assert result["action"] == (
            "SKIPPED_NO_PAYLOAD"
        )
        assert result["state"][
            "consecutive_failures"
        ] == 0


def test_not_due_runner_skips() -> None:
    with build_session() as session:
        repository = SchedulerStateRepository(
            session
        )
        state = repository.update(
            enabled=True,
            interval_seconds=300,
        )

        runner = SafeSchedulerRunner(
            state_repository=repository,
            cycle_callback=lambda: {
                "status": "COMPLETED"
            },
        )

        now = datetime.now(timezone.utc)
        state.next_run_at = (
            now + timedelta(minutes=5)
        )
        session.commit()

        result = runner.tick(now=now)

        assert result["action"] == (
            "SKIPPED_NOT_DUE"
        )


def test_forced_tick_executes_callback() -> None:
    with build_session() as session:
        repository = SchedulerStateRepository(
            session
        )
        calls = 0

        def callback():
            nonlocal calls
            calls += 1

            return {
                "cycle_id": 10,
                "status": "COMPLETED",
            }

        runner = SafeSchedulerRunner(
            state_repository=repository,
            cycle_callback=callback,
        )

        result = runner.tick(force=True)

        assert result["action"] == "EXECUTED"
        assert result["cycle"]["cycle_id"] == 10
        assert calls == 1


def test_failures_auto_disable_scheduler() -> None:
    with build_session() as session:
        repository = SchedulerStateRepository(
            session
        )
        repository.update(
            enabled=True,
            interval_seconds=60,
        )

        def callback():
            raise RuntimeError(
                "Synthetic runner failure."
            )

        runner = SafeSchedulerRunner(
            state_repository=repository,
            cycle_callback=callback,
        )

        first = runner.tick(force=True)
        second = runner.tick(force=True)
        third = runner.tick(force=True)

        assert first["state"][
            "consecutive_failures"
        ] == 1
        assert second["state"][
            "consecutive_failures"
        ] == 2
        assert third["state"][
            "consecutive_failures"
        ] == 3
        assert third["state"]["enabled"] is False


def test_successful_cycle_resets_failures() -> None:
    with build_session() as session:
        repository = SchedulerStateRepository(
            session
        )
        repository.record_runner_failure(
            occurred_at=datetime.now(
                timezone.utc
            ),
            disable_threshold=3,
        )

        repository.update(
            enabled=True,
            interval_seconds=60,
        )

        def callback():
            state = repository.record_cycle(
                cycle_id=12,
                cycle_status="COMPLETED",
                finished_at=datetime.now(
                    timezone.utc
                ),
            )

            return {
                "cycle_id": state.last_cycle_id,
                "status": "COMPLETED",
            }

        runner = SafeSchedulerRunner(
            state_repository=repository,
            cycle_callback=callback,
        )

        result = runner.tick(force=True)

        assert result["action"] == "EXECUTED"
        assert result["state"][
            "consecutive_failures"
        ] == 0


def test_status_tracks_last_tick() -> None:
    with build_session() as session:
        repository = SchedulerStateRepository(
            session
        )
        runner = SafeSchedulerRunner(
            state_repository=repository,
            cycle_callback=lambda: None,
        )

        runner.tick()

        status = runner.status()

        assert status.running is False
        assert status.last_tick_at is not None
        assert status.last_action == (
            "SKIPPED_DISABLED"
        )
