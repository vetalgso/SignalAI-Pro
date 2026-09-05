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
from app.tradinggpt.scheduler.observability import (
    SchedulerObservabilityService,
)
from app.tradinggpt.scheduler.payload_repository import (
    SchedulerPayloadRepository,
)
from app.tradinggpt.scheduler.payload_service import (
    SchedulerPayloadService,
)
from app.tradinggpt.scheduler.repository import (
    SchedulerCycleRepository,
)
from app.tradinggpt.scheduler.schemas import (
    SchedulerObservabilityResponse,
)
from app.tradinggpt.scheduler.state_repository import (
    SchedulerStateRepository,
)
from app.tradinggpt.scheduler.state_service import (
    SchedulerStateService,
)


NOW = datetime(
    2026,
    8,
    3,
    13,
    0,
    tzinfo=timezone.utc,
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


def background_status(
    *,
    running: bool = True,
    stopping: bool = False,
    failed_ticks: int = 0,
    last_error: str | None = None,
) -> dict[str, object]:
    return {
        "running": running,
        "stopping": stopping,
        "poll_interval_seconds": 5.0,
        "iterations": 10,
        "failed_ticks": failed_ticks,
        "started_at": NOW - timedelta(minutes=5),
        "stopped_at": None,
        "last_tick_started_at": (
            NOW - timedelta(seconds=5)
        ),
        "last_tick_finished_at": (
            NOW - timedelta(seconds=4)
        ),
        "last_action": "SKIPPED_DISABLED",
        "last_error": last_error,
    }


def build_service(
    session: Session,
    *,
    background: dict[str, object] | None = None,
    background_loop_enabled: bool = True,
    distributed_lock_enabled: bool = True,
) -> SchedulerObservabilityService:
    return SchedulerObservabilityService(
        state_service=SchedulerStateService(
            SchedulerStateRepository(session)
        ),
        payload_service=SchedulerPayloadService(
            SchedulerPayloadRepository(session)
        ),
        cycle_repository=SchedulerCycleRepository(
            session
        ),
        background_status_provider=lambda: (
            background
            if background is not None
            else background_status()
        ),
        background_loop_enabled=(
            background_loop_enabled
        ),
        distributed_lock_enabled=(
            distributed_lock_enabled
        ),
        distributed_lock_backend=(
            "postgresql_advisory"
        ),
        advisory_lock_key=2026080320,
        now_provider=lambda: NOW,
    )


def configure_payload(
    session: Session,
) -> None:
    SchedulerPayloadRepository(session).save(
        runtime_risk_payload={
            "equity": 10_000.0,
        },
        analysis_payload={
            "dry_run": True,
            "idempotency_key": "base-key",
            "execution": {
                "symbol": "BTCUSDT",
            },
            "order_routing": {
                "exchange": "PAPER",
                "market_type": "SPOT",
            },
        },
    )


def set_next_run(
    session: Session,
    value: datetime,
) -> None:
    state = SchedulerStateRepository(
        session
    ).get_or_create()
    state.next_run_at = value
    session.add(state)
    session.commit()


def test_disabled_scheduler_reports_standby() -> None:
    with build_session() as session:
        result = build_service(session).get()

        validated = (
            SchedulerObservabilityResponse
            .model_validate(result)
        )

        assert validated.status == "STANDBY"
        assert validated.healthy is True
        assert validated.execution_ready is False
        assert validated.blockers == []
        assert validated.payload.configured is False
        assert validated.last_cycle is None


def test_enabled_ready_scheduler_reports_active() -> None:
    with build_session() as session:
        SchedulerStateRepository(session).update(
            enabled=True,
            interval_seconds=60,
        )
        set_next_run(
            session,
            NOW + timedelta(seconds=45),
        )
        configure_payload(session)

        result = build_service(session).get()
        validated = (
            SchedulerObservabilityResponse
            .model_validate(result)
        )

        assert validated.status == "ACTIVE"
        assert validated.healthy is True
        assert validated.execution_ready is True
        assert validated.next_run_due is False
        assert validated.seconds_until_next_run == 45
        assert validated.payload.exchange == "PAPER"
        assert validated.payload.symbol == "BTCUSDT"


def test_enabled_without_payload_is_degraded() -> None:
    with build_session() as session:
        SchedulerStateRepository(session).update(
            enabled=True,
            interval_seconds=60,
        )
        set_next_run(
            session,
            NOW + timedelta(seconds=30),
        )

        result = build_service(session).get()

        assert result["status"] == "DEGRADED"
        assert result["healthy"] is False
        assert result["execution_ready"] is False
        assert any(
            "no persisted payload" in blocker
            for blocker in result["blockers"]
        )


def test_stopped_background_loop_is_degraded() -> None:
    with build_session() as session:
        result = build_service(
            session,
            background=background_status(
                running=False
            ),
        ).get()

        assert result["status"] == "DEGRADED"
        assert result["healthy"] is False
        assert any(
            "not running" in blocker
            for blocker in result["blockers"]
        )


def test_last_cycle_and_overdue_slot_are_summarized() -> None:
    with build_session() as session:
        state_repository = (
            SchedulerStateRepository(session)
        )
        state_repository.update(
            enabled=True,
            interval_seconds=60,
        )
        set_next_run(
            session,
            NOW - timedelta(seconds=3),
        )
        configure_payload(session)

        repository = SchedulerCycleRepository(
            session
        )
        cycle = repository.create_started(
            dry_run=True
        )
        repository.finish(
            cycle=cycle,
            status="COMPLETED",
            risk_payload={
                "status": "ALLOW",
            },
            execution_payload={
                "action": "DRY_RUN",
                "journal": {
                    "idempotency_key": (
                        "scheduler-slot-test"
                    ),
                    "exchange": "PAPER",
                    "market_type": "SPOT",
                    "symbol": "BTCUSDT",
                    "replayed": False,
                    "simulated": True,
                },
            },
        )

        result = build_service(session).get()
        validated = (
            SchedulerObservabilityResponse
            .model_validate(result)
        )

        assert validated.next_run_due is True
        assert validated.seconds_until_next_run == 0
        assert validated.last_cycle is not None
        assert validated.last_cycle.cycle_id == cycle.id
        assert (
            validated.last_cycle.execution_action
            == "DRY_RUN"
        )
        assert (
            validated.last_cycle.idempotency_key
            == "scheduler-slot-test"
        )
        assert validated.last_cycle.replayed is False
        assert validated.last_cycle.simulated is True
