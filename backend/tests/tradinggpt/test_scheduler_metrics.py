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
from app.tradinggpt.scheduler.metrics import (
    SchedulerMetricsService,
)
from app.tradinggpt.scheduler.repository import (
    SchedulerCycleRepository,
)


NOW = datetime(
    2026,
    8,
    3,
    14,
    0,
    tzinfo=timezone.utc,
)


def observability(
    *,
    status: str = "STANDBY",
    enabled: bool = False,
    configured: bool = False,
    next_run_at: datetime | None = None,
    next_run_due: bool = False,
    seconds_until_next_run: int | None = None,
    last_cycle: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "generated_at": NOW,
        "status": status,
        "next_run_due": next_run_due,
        "seconds_until_next_run": (
            seconds_until_next_run
        ),
        "state": {
            "enabled": enabled,
            "next_run_at": next_run_at,
            "consecutive_failures": 0,
        },
        "payload": {
            "configured": configured,
        },
        "background": {
            "running": True,
            "stopping": False,
            "iterations": 12,
            "failed_ticks": 0,
            "last_tick_finished_at": (
                NOW - timedelta(seconds=5)
            ),
        },
        "distributed_lock": {
            "enabled": True,
        },
        "last_cycle": last_cycle,
    }


def readiness(
    *,
    ready: bool = True,
    reason_codes: list[str] | None = None,
    warning_codes: list[str] | None = None,
) -> dict[str, object]:
    return {
        "ready": ready,
        "reason_codes": reason_codes or [],
        "warning_codes": warning_codes or [],
        "checks": [
            {
                "status": "PASS",
            },
            {
                "status": "PASS",
            },
            {
                "status": (
                    "FAIL"
                    if not ready
                    else "PASS"
                ),
            },
        ],
    }


def render(
    snapshot: dict[str, object],
    readiness_snapshot: dict[str, object],
    counts: dict[str, int] | None = None,
) -> str:
    return SchedulerMetricsService(
        observability_provider=lambda: snapshot,
        readiness_provider=lambda: (
            readiness_snapshot
        ),
        cycle_counts_provider=lambda: (
            counts or {}
        ),
    ).render()


def test_standby_metrics_are_rendered() -> None:
    result = render(
        observability(),
        readiness(),
    )

    assert result.endswith("\n")
    assert (
        "# TYPE signalai_scheduler_ready gauge"
        in result
    )
    assert "signalai_scheduler_ready 1" in result
    assert (
        'signalai_scheduler_status'
        '{status="STANDBY"} 1'
        in result
    )
    assert (
        'signalai_scheduler_status'
        '{status="ACTIVE"} 0'
        in result
    )
    assert (
        "signalai_scheduler_enabled 0"
        in result
    )
    assert (
        "signalai_scheduler_payload_configured 0"
        in result
    )


def test_active_next_run_metrics_are_rendered() -> None:
    result = render(
        observability(
            status="ACTIVE",
            enabled=True,
            configured=True,
            next_run_at=NOW + timedelta(
                seconds=30
            ),
            seconds_until_next_run=30,
        ),
        readiness(),
    )

    assert (
        'signalai_scheduler_status'
        '{status="ACTIVE"} 1'
        in result
    )
    assert (
        "signalai_scheduler_next_run_scheduled 1"
        in result
    )
    assert (
        "signalai_scheduler_seconds_until_next_run 30"
        in result
    )


def test_readiness_failure_codes_are_rendered() -> None:
    result = render(
        observability(status="DEGRADED"),
        readiness(
            ready=False,
            reason_codes=[
                "SCHEDULER_PAYLOAD_MISSING",
            ],
            warning_codes=[
                "LAST_CYCLE_FAILED",
            ],
        ),
    )

    assert "signalai_scheduler_ready 0" in result
    assert (
        'signalai_scheduler_readiness_failure'
        '{code="SCHEDULER_PAYLOAD_MISSING"} 1'
        in result
    )
    assert (
        'signalai_scheduler_readiness_warning'
        '{code="LAST_CYCLE_FAILED"} 1'
        in result
    )
    assert (
        'signalai_scheduler_readiness_checks'
        '{status="FAIL"} 1'
        in result
    )


def test_cycle_counts_include_zero_statuses() -> None:
    result = render(
        observability(),
        readiness(),
        counts={
            "COMPLETED": 4,
            "FAILED": 2,
        },
    )

    assert (
        'signalai_scheduler_cycles_total'
        '{status="COMPLETED"} 4'
        in result
    )
    assert (
        'signalai_scheduler_cycles_total'
        '{status="FAILED"} 2'
        in result
    )
    assert (
        'signalai_scheduler_cycles_total'
        '{status="STARTED"} 0'
        in result
    )


def test_last_cycle_duration_is_rendered() -> None:
    started_at = NOW - timedelta(
        seconds=2.5
    )

    result = render(
        observability(
            last_cycle={
                "status": "COMPLETED",
                "started_at": started_at,
                "finished_at": NOW,
                "simulated": True,
                "replayed": False,
            },
        ),
        readiness(),
    )

    assert (
        "signalai_scheduler_last_cycle_present 1"
        in result
    )
    assert (
        "signalai_scheduler_"
        "last_cycle_duration_seconds 2.5"
        in result
    )
    assert (
        'signalai_scheduler_last_cycle_status'
        '{status="COMPLETED"} 1'
        in result
    )
    assert (
        "signalai_scheduler_last_cycle_simulated 1"
        in result
    )
    assert (
        "signalai_scheduler_last_cycle_replayed 0"
        in result
    )


def test_missing_last_cycle_uses_zero_values() -> None:
    result = render(
        observability(last_cycle=None),
        readiness(),
    )

    assert (
        "signalai_scheduler_last_cycle_present 0"
        in result
    )
    assert (
        "signalai_scheduler_"
        "last_cycle_duration_seconds 0"
        in result
    )
    assert (
        "signalai_scheduler_"
        "last_cycle_finished_timestamp_seconds 0"
        in result
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


def test_repository_counts_cycles_by_status() -> None:
    with build_session() as session:
        repository = SchedulerCycleRepository(
            session
        )

        first = repository.create_started()
        repository.finish(
            cycle=first,
            status="COMPLETED",
            risk_payload=None,
            execution_payload=None,
        )

        second = repository.create_started()
        repository.finish(
            cycle=second,
            status="FAILED",
            risk_payload=None,
            execution_payload=None,
            error_message="failure",
        )

        repository.create_started()

        assert repository.count_by_status() == {
            "COMPLETED": 1,
            "FAILED": 1,
            "STARTED": 1,
        }
