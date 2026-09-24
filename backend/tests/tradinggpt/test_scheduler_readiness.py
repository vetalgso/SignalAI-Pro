from __future__ import annotations

from datetime import datetime, timezone

from app.tradinggpt.scheduler.readiness import (
    SchedulerReadinessService,
)
from app.tradinggpt.scheduler.schemas import (
    SchedulerReadinessResponse,
)


NOW = datetime(
    2026,
    8,
    3,
    13,
    30,
    tzinfo=timezone.utc,
)


def observability(
    *,
    scheduler_status: str = "STANDBY",
    scheduler_enabled: bool = False,
    payload_configured: bool = False,
    next_run_at: datetime | None = None,
    background_running: bool = True,
    background_stopping: bool = False,
    background_error: str | None = None,
    failed_ticks: int = 0,
    consecutive_failures: int = 0,
    distributed_lock_enabled: bool = True,
    last_cycle_status: str | None = "COMPLETED",
) -> dict[str, object]:
    last_cycle: dict[str, object] | None

    if last_cycle_status is None:
        last_cycle = None
    else:
        last_cycle = {
            "cycle_id": 1,
            "status": last_cycle_status,
        }

    return {
        "generated_at": NOW,
        "status": scheduler_status,
        "healthy": scheduler_status != "DEGRADED",
        "execution_ready": (
            scheduler_status == "ACTIVE"
        ),
        "state": {
            "enabled": scheduler_enabled,
            "next_run_at": next_run_at,
            "consecutive_failures": (
                consecutive_failures
            ),
        },
        "payload": {
            "configured": payload_configured,
        },
        "background": {
            "running": background_running,
            "stopping": background_stopping,
            "last_error": background_error,
            "failed_ticks": failed_ticks,
        },
        "distributed_lock": {
            "enabled": distributed_lock_enabled,
        },
        "last_cycle": last_cycle,
    }


def build_service(
    snapshot: dict[str, object],
    *,
    background_loop_enabled: bool = True,
) -> SchedulerReadinessService:
    return SchedulerReadinessService(
        observability_provider=lambda: snapshot,
        background_loop_enabled=(
            background_loop_enabled
        ),
    )


def test_standby_runtime_is_ready() -> None:
    result = build_service(
        observability()
    ).get()

    validated = (
        SchedulerReadinessResponse
        .model_validate(result)
    )

    assert validated.status == "READY"
    assert validated.ready is True
    assert validated.scheduler_status == "STANDBY"
    assert validated.reason_codes == []
    assert validated.warning_codes == []


def test_active_runtime_is_ready() -> None:
    result = build_service(
        observability(
            scheduler_status="ACTIVE",
            scheduler_enabled=True,
            payload_configured=True,
            next_run_at=NOW,
        )
    ).get()

    assert result["status"] == "READY"
    assert result["ready"] is True
    assert result["reason_codes"] == []


def test_enabled_without_payload_is_not_ready() -> None:
    result = build_service(
        observability(
            scheduler_status="DEGRADED",
            scheduler_enabled=True,
            payload_configured=False,
            next_run_at=NOW,
        )
    ).get()

    assert result["status"] == "NOT_READY"
    assert result["ready"] is False
    assert (
        "SCHEDULER_PAYLOAD_MISSING"
        in result["reason_codes"]
    )


def test_missing_next_run_is_not_ready() -> None:
    result = build_service(
        observability(
            scheduler_status="DEGRADED",
            scheduler_enabled=True,
            payload_configured=True,
            next_run_at=None,
        )
    ).get()

    assert result["ready"] is False
    assert (
        "SCHEDULER_NEXT_RUN_MISSING"
        in result["reason_codes"]
    )


def test_background_failures_are_not_ready() -> None:
    result = build_service(
        observability(
            scheduler_status="DEGRADED",
            background_running=False,
            background_stopping=True,
            background_error="loop failure",
        )
    ).get()

    assert result["ready"] is False
    assert set(result["reason_codes"]) >= {
        "BACKGROUND_LOOP_NOT_RUNNING",
        "BACKGROUND_LOOP_STOPPING",
        "BACKGROUND_LOOP_ERROR",
    }


def test_disabled_lock_is_warning_in_standby() -> None:
    result = build_service(
        observability(
            distributed_lock_enabled=False,
        )
    ).get()

    assert result["ready"] is True
    assert result["reason_codes"] == []
    assert (
        "DISTRIBUTED_LOCK_DISABLED"
        in result["warning_codes"]
    )


def test_disabled_lock_is_failure_when_active() -> None:
    result = build_service(
        observability(
            scheduler_status="DEGRADED",
            scheduler_enabled=True,
            payload_configured=True,
            next_run_at=NOW,
            distributed_lock_enabled=False,
        )
    ).get()

    assert result["ready"] is False
    assert (
        "DISTRIBUTED_LOCK_DISABLED"
        in result["reason_codes"]
    )


def test_runtime_history_produces_warnings() -> None:
    result = build_service(
        observability(
            failed_ticks=2,
            consecutive_failures=1,
            last_cycle_status="FAILED",
        )
    ).get()

    assert result["ready"] is True
    assert result["reason_codes"] == []
    assert set(result["warning_codes"]) == {
        "BACKGROUND_FAILED_TICKS",
        "SCHEDULER_CONSECUTIVE_FAILURES",
        "LAST_CYCLE_FAILED",
    }


def test_disabled_background_loop_fails_when_active() -> None:
    result = build_service(
        observability(
            scheduler_status="DEGRADED",
            scheduler_enabled=True,
            payload_configured=True,
            next_run_at=NOW,
            background_running=False,
        ),
        background_loop_enabled=False,
    ).get()

    assert result["ready"] is False
    assert (
        "BACKGROUND_LOOP_DISABLED"
        in result["reason_codes"]
    )
