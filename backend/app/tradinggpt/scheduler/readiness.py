from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


class SchedulerReadinessService:
    """
    Convert scheduler observability into a stable
    machine-readable readiness contract.

    The service is read-only and does not mutate
    scheduler runtime state.
    """

    def __init__(
        self,
        *,
        observability_provider: Callable[
            [],
            Mapping[str, object],
        ],
        background_loop_enabled: bool,
    ) -> None:
        self._observability_provider = (
            observability_provider
        )
        self._background_loop_enabled = (
            background_loop_enabled
        )

    def get(self) -> dict[str, object]:
        observability = dict(
            self._observability_provider()
        )

        state = self._mapping(
            observability.get("state"),
            name="state",
        )
        payload = self._mapping(
            observability.get("payload"),
            name="payload",
        )
        background = self._mapping(
            observability.get("background"),
            name="background",
        )
        distributed_lock = self._mapping(
            observability.get(
                "distributed_lock"
            ),
            name="distributed_lock",
        )

        scheduler_status = self._string(
            observability.get("status"),
            name="status",
        )
        scheduler_enabled = bool(
            state.get("enabled")
        )
        payload_configured = bool(
            payload.get("configured")
        )
        background_running = bool(
            background.get("running")
        )
        background_stopping = bool(
            background.get("stopping")
        )
        background_error = background.get(
            "last_error"
        )
        failed_ticks = int(
            background.get("failed_ticks") or 0
        )
        consecutive_failures = int(
            state.get("consecutive_failures")
            or 0
        )
        next_run_at = state.get("next_run_at")
        lock_enabled = bool(
            distributed_lock.get("enabled")
        )

        checks: list[dict[str, object]] = []

        if self._background_loop_enabled:
            if background_running:
                self._add_check(
                    checks,
                    name="background_loop_running",
                    status="PASS",
                    code="BACKGROUND_LOOP_RUNNING",
                    message=(
                        "Background scheduler loop "
                        "is running."
                    ),
                )
            else:
                self._add_check(
                    checks,
                    name="background_loop_running",
                    status="FAIL",
                    code=(
                        "BACKGROUND_LOOP_NOT_RUNNING"
                    ),
                    message=(
                        "Background scheduler loop "
                        "is configured but not running."
                    ),
                )
        elif scheduler_enabled:
            self._add_check(
                checks,
                name="background_loop_configuration",
                status="FAIL",
                code="BACKGROUND_LOOP_DISABLED",
                message=(
                    "Scheduler is enabled while the "
                    "background loop is disabled."
                ),
            )
        else:
            self._add_check(
                checks,
                name="background_loop_configuration",
                status="WARN",
                code="BACKGROUND_LOOP_DISABLED",
                message=(
                    "Background scheduler loop is "
                    "disabled by configuration."
                ),
            )

        if background_stopping:
            self._add_check(
                checks,
                name="background_loop_stopping",
                status="FAIL",
                code="BACKGROUND_LOOP_STOPPING",
                message=(
                    "Background scheduler loop is "
                    "stopping."
                ),
            )
        else:
            self._add_check(
                checks,
                name="background_loop_stopping",
                status="PASS",
                code="BACKGROUND_LOOP_STABLE",
                message=(
                    "Background scheduler loop is "
                    "not stopping."
                ),
            )

        if background_error is not None:
            self._add_check(
                checks,
                name="background_loop_error",
                status="FAIL",
                code="BACKGROUND_LOOP_ERROR",
                message=(
                    "Background scheduler loop "
                    f"reports an error: "
                    f"{background_error}"
                ),
            )
        else:
            self._add_check(
                checks,
                name="background_loop_error",
                status="PASS",
                code="BACKGROUND_LOOP_ERROR_FREE",
                message=(
                    "Background scheduler loop "
                    "reports no error."
                ),
            )

        if scheduler_enabled and not payload_configured:
            self._add_check(
                checks,
                name="scheduler_payload",
                status="FAIL",
                code="SCHEDULER_PAYLOAD_MISSING",
                message=(
                    "Scheduler is enabled without "
                    "a persisted payload."
                ),
            )
        else:
            self._add_check(
                checks,
                name="scheduler_payload",
                status="PASS",
                code=(
                    "SCHEDULER_PAYLOAD_CONFIGURED"
                    if payload_configured
                    else "SCHEDULER_PAYLOAD_NOT_REQUIRED"
                ),
                message=(
                    "Persisted scheduler payload "
                    "is configured."
                    if payload_configured
                    else
                    "Persisted payload is not "
                    "required while scheduler is "
                    "disabled."
                ),
            )

        if scheduler_enabled and next_run_at is None:
            self._add_check(
                checks,
                name="next_run_schedule",
                status="FAIL",
                code="SCHEDULER_NEXT_RUN_MISSING",
                message=(
                    "Scheduler is enabled but "
                    "next_run_at is not set."
                ),
            )
        else:
            self._add_check(
                checks,
                name="next_run_schedule",
                status="PASS",
                code=(
                    "SCHEDULER_NEXT_RUN_SCHEDULED"
                    if next_run_at is not None
                    else
                    "SCHEDULER_NEXT_RUN_NOT_REQUIRED"
                ),
                message=(
                    "The next scheduler run is "
                    "scheduled."
                    if next_run_at is not None
                    else
                    "A next run is not required "
                    "while scheduler is disabled."
                ),
            )

        if lock_enabled:
            self._add_check(
                checks,
                name="distributed_lock",
                status="PASS",
                code="DISTRIBUTED_LOCK_ENABLED",
                message=(
                    "Distributed scheduler execution "
                    "locking is enabled."
                ),
            )
        elif scheduler_enabled:
            self._add_check(
                checks,
                name="distributed_lock",
                status="FAIL",
                code="DISTRIBUTED_LOCK_DISABLED",
                message=(
                    "Scheduler is enabled without "
                    "distributed execution locking."
                ),
            )
        else:
            self._add_check(
                checks,
                name="distributed_lock",
                status="WARN",
                code="DISTRIBUTED_LOCK_DISABLED",
                message=(
                    "Distributed scheduler execution "
                    "locking is disabled."
                ),
            )

        if failed_ticks > 0:
            self._add_check(
                checks,
                name="background_failed_ticks",
                status="WARN",
                code="BACKGROUND_FAILED_TICKS",
                message=(
                    "Background scheduler loop has "
                    f"recorded {failed_ticks} failed "
                    "tick(s)."
                ),
            )
        else:
            self._add_check(
                checks,
                name="background_failed_ticks",
                status="PASS",
                code="BACKGROUND_TICKS_HEALTHY",
                message=(
                    "Background scheduler loop has "
                    "no failed ticks."
                ),
            )

        if consecutive_failures > 0:
            self._add_check(
                checks,
                name="scheduler_failure_state",
                status="WARN",
                code=(
                    "SCHEDULER_CONSECUTIVE_FAILURES"
                ),
                message=(
                    "Scheduler state contains "
                    f"{consecutive_failures} "
                    "consecutive failure(s)."
                ),
            )
        else:
            self._add_check(
                checks,
                name="scheduler_failure_state",
                status="PASS",
                code="SCHEDULER_FAILURE_STATE_CLEAR",
                message=(
                    "Scheduler has no consecutive "
                    "failures."
                ),
            )

        last_cycle = observability.get(
            "last_cycle"
        )

        if isinstance(last_cycle, Mapping):
            last_cycle_status = last_cycle.get(
                "status"
            )

            if last_cycle_status == "FAILED":
                self._add_check(
                    checks,
                    name="last_cycle",
                    status="WARN",
                    code="LAST_CYCLE_FAILED",
                    message=(
                        "The latest scheduler cycle "
                        "failed."
                    ),
                )
            else:
                self._add_check(
                    checks,
                    name="last_cycle",
                    status="PASS",
                    code="LAST_CYCLE_HEALTHY",
                    message=(
                        "The latest scheduler cycle "
                        "did not fail."
                    ),
                )
        else:
            self._add_check(
                checks,
                name="last_cycle",
                status="PASS",
                code="LAST_CYCLE_NOT_AVAILABLE",
                message=(
                    "No scheduler cycle has been "
                    "recorded yet."
                ),
            )

        failed_checks = [
            check
            for check in checks
            if check["status"] == "FAIL"
        ]

        if (
            scheduler_status == "DEGRADED"
            and not failed_checks
        ):
            self._add_check(
                checks,
                name="observability_status",
                status="FAIL",
                code="OBSERVABILITY_DEGRADED",
                message=(
                    "Scheduler observability reports "
                    "a degraded runtime."
                ),
            )
            failed_checks = [
                check
                for check in checks
                if check["status"] == "FAIL"
            ]

        warning_checks = [
            check
            for check in checks
            if check["status"] == "WARN"
        ]

        ready = (
            scheduler_status != "DEGRADED"
            and not failed_checks
        )

        return {
            "generated_at": observability.get(
                "generated_at"
            ),
            "status": (
                "READY"
                if ready
                else "NOT_READY"
            ),
            "ready": ready,
            "scheduler_status": scheduler_status,
            "reason_codes": [
                str(check["code"])
                for check in failed_checks
            ],
            "warning_codes": [
                str(check["code"])
                for check in warning_checks
            ],
            "checks": checks,
        }

    @staticmethod
    def _add_check(
        checks: list[dict[str, object]],
        *,
        name: str,
        status: str,
        code: str,
        message: str,
    ) -> None:
        checks.append(
            {
                "name": name,
                "status": status,
                "code": code,
                "message": message,
            }
        )

    @staticmethod
    def _mapping(
        value: Any,
        *,
        name: str,
    ) -> Mapping[str, object]:
        if not isinstance(value, Mapping):
            raise TypeError(
                "Scheduler observability "
                f"{name} must be a mapping."
            )

        return value

    @staticmethod
    def _string(
        value: Any,
        *,
        name: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(
                "Scheduler observability "
                f"{name} must be a string."
            )

        return value
