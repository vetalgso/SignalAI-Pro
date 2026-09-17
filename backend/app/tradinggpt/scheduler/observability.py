from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from .payload_service import SchedulerPayloadService
from .repository import SchedulerCycleRepository
from .state_service import SchedulerStateService


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SchedulerObservabilityService:
    """
    Build one operational view of scheduler runtime.

    The service is read-only. It does not enable the
    scheduler, mutate payloads or execute trading cycles.
    """

    def __init__(
        self,
        *,
        state_service: SchedulerStateService,
        payload_service: SchedulerPayloadService,
        cycle_repository: SchedulerCycleRepository,
        background_status_provider: Callable[
            [],
            Mapping[str, object],
        ],
        background_loop_enabled: bool,
        distributed_lock_enabled: bool,
        distributed_lock_backend: str,
        advisory_lock_key: int | None,
        now_provider: Callable[
            [],
            datetime,
        ] = _utc_now,
    ) -> None:
        self._state_service = state_service
        self._payload_service = payload_service
        self._cycle_repository = cycle_repository
        self._background_status_provider = (
            background_status_provider
        )
        self._background_loop_enabled = (
            background_loop_enabled
        )
        self._distributed_lock_enabled = (
            distributed_lock_enabled
        )
        self._distributed_lock_backend = (
            distributed_lock_backend
        )
        self._advisory_lock_key = advisory_lock_key
        self._now_provider = now_provider

    def get(self) -> dict[str, object]:
        generated_at = self._as_utc(
            self._now_provider()
        )
        state = self._state_service.get()
        payload = self._payload_service.get()
        background = dict(
            self._background_status_provider()
        )

        payload_summary = self._payload_summary(
            payload
        )
        last_cycle = self._last_cycle_summary()

        blockers: list[str] = []
        warnings: list[str] = []

        scheduler_enabled = bool(
            state["enabled"]
        )
        payload_configured = bool(
            payload_summary["configured"]
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
            state["consecutive_failures"]
        )

        if self._background_loop_enabled:
            if not background_running:
                blockers.append(
                    "Background scheduler loop is "
                    "configured but not running."
                )
        else:
            warnings.append(
                "Background scheduler loop is "
                "disabled by configuration."
            )

        if background_stopping:
            blockers.append(
                "Background scheduler loop is stopping."
            )

        if background_error:
            blockers.append(
                "Background scheduler loop reports "
                f"an error: {background_error}"
            )

        if failed_ticks > 0:
            warnings.append(
                "Background scheduler loop has "
                f"recorded {failed_ticks} failed "
                "tick(s)."
            )

        if consecutive_failures > 0:
            warnings.append(
                "Scheduler state contains "
                f"{consecutive_failures} consecutive "
                "failure(s)."
            )

        if not self._distributed_lock_enabled:
            warnings.append(
                "Distributed scheduler execution "
                "locking is disabled."
            )

        next_run_at = state["next_run_at"]

        if scheduler_enabled:
            if not payload_configured:
                blockers.append(
                    "Scheduler is enabled but no "
                    "persisted payload is configured."
                )

            if not self._background_loop_enabled:
                blockers.append(
                    "Scheduler is enabled while the "
                    "background loop is disabled."
                )

            if not self._distributed_lock_enabled:
                blockers.append(
                    "Scheduler is enabled without "
                    "distributed execution locking."
                )

            if next_run_at is None:
                blockers.append(
                    "Scheduler is enabled but "
                    "next_run_at is not set."
                )

        if (
            last_cycle is not None
            and last_cycle["status"] == "FAILED"
        ):
            warnings.append(
                "The latest scheduler cycle failed."
            )

        (
            next_run_due,
            seconds_until_next_run,
        ) = self._next_run_timing(
            next_run_at=next_run_at,
            generated_at=generated_at,
        )

        healthy = not blockers
        execution_ready = (
            healthy
            and scheduler_enabled
            and payload_configured
            and background_running
            and not background_stopping
            and self._distributed_lock_enabled
        )

        if blockers:
            runtime_status = "DEGRADED"
        elif scheduler_enabled:
            runtime_status = "ACTIVE"
        else:
            runtime_status = "STANDBY"

        return {
            "generated_at": generated_at,
            "status": runtime_status,
            "healthy": healthy,
            "execution_ready": execution_ready,
            "next_run_due": next_run_due,
            "seconds_until_next_run": (
                seconds_until_next_run
            ),
            "blockers": blockers,
            "warnings": warnings,
            "state": state,
            "payload": payload_summary,
            "background": background,
            "distributed_lock": {
                "enabled": (
                    self._distributed_lock_enabled
                ),
                "backend": (
                    self._distributed_lock_backend
                ),
                "lock_key": (
                    self._advisory_lock_key
                ),
            },
            "last_cycle": last_cycle,
        }

    @staticmethod
    def _payload_summary(
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        raw_analysis = payload.get(
            "analysis_payload"
        )
        analysis = (
            raw_analysis
            if isinstance(raw_analysis, dict)
            else {}
        )

        raw_routing = analysis.get(
            "order_routing"
        )
        routing = (
            raw_routing
            if isinstance(raw_routing, dict)
            else {}
        )

        raw_execution = analysis.get(
            "execution"
        )
        execution = (
            raw_execution
            if isinstance(raw_execution, dict)
            else {}
        )

        dry_run = analysis.get("dry_run")
        idempotency_key = analysis.get(
            "idempotency_key"
        )
        exchange = routing.get("exchange")
        market_type = routing.get(
            "market_type"
        )
        symbol = execution.get("symbol")

        return {
            "configured": bool(
                payload["configured"]
            ),
            "dry_run": (
                dry_run
                if isinstance(dry_run, bool)
                else None
            ),
            "exchange": (
                exchange
                if isinstance(exchange, str)
                else None
            ),
            "market_type": (
                market_type
                if isinstance(market_type, str)
                else None
            ),
            "symbol": (
                symbol
                if isinstance(symbol, str)
                else None
            ),
            "idempotency_key": (
                idempotency_key
                if isinstance(
                    idempotency_key,
                    str,
                )
                else None
            ),
            "updated_at": payload["updated_at"],
        }

    def _last_cycle_summary(
        self,
    ) -> dict[str, object] | None:
        cycles = self._cycle_repository.list_recent(
            limit=1
        )

        if not cycles:
            return None

        cycle = cycles[0]
        raw_execution = cycle.execution_payload

        execution = (
            raw_execution
            if isinstance(raw_execution, dict)
            else {}
        )
        raw_journal = execution.get("journal")
        journal = (
            raw_journal
            if isinstance(raw_journal, dict)
            else {}
        )

        return {
            "cycle_id": cycle.id,
            "status": cycle.status,
            "dry_run": cycle.dry_run,
            "started_at": cycle.started_at,
            "finished_at": cycle.finished_at,
            "error_message": cycle.error_message,
            "execution_action": (
                self._optional_string(
                    execution.get("action")
                )
            ),
            "idempotency_key": (
                self._optional_string(
                    journal.get(
                        "idempotency_key"
                    )
                )
            ),
            "exchange": self._optional_string(
                journal.get("exchange")
            ),
            "market_type": (
                self._optional_string(
                    journal.get("market_type")
                )
            ),
            "symbol": self._optional_string(
                journal.get("symbol")
            ),
            "replayed": self._optional_bool(
                journal.get("replayed")
            ),
            "simulated": self._optional_bool(
                journal.get("simulated")
            ),
        }

    @classmethod
    def _next_run_timing(
        cls,
        *,
        next_run_at: object,
        generated_at: datetime,
    ) -> tuple[bool, int | None]:
        if not isinstance(
            next_run_at,
            datetime,
        ):
            return False, None

        normalized = cls._as_utc(next_run_at)
        remaining = (
            normalized - generated_at
        ).total_seconds()

        return (
            remaining <= 0,
            max(0, math.ceil(remaining)),
        )

    @staticmethod
    def _optional_string(
        value: Any,
    ) -> str | None:
        return value if isinstance(value, str) else None

    @staticmethod
    def _optional_bool(
        value: Any,
    ) -> bool | None:
        return value if isinstance(value, bool) else None

    @staticmethod
    def _as_utc(
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(timezone.utc)
