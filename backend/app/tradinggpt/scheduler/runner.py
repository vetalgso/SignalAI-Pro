from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from .state_repository import (
    SchedulerStateRepository,
)


@dataclass(frozen=True, slots=True)
class SchedulerRunnerStatus:
    running: bool
    last_tick_at: datetime | None
    last_action: str | None
    last_error: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class SafeSchedulerRunner:
    """
    Execute at most one scheduler tick at a time.

    This class does not create its own infinite loop yet.
    A tick must be triggered explicitly by the API or tests.
    """

    FAILURE_DISABLE_THRESHOLD = 3

    def __init__(
        self,
        *,
        state_repository: SchedulerStateRepository,
        cycle_callback: Callable[
            [],
            dict[str, Any] | None,
        ],
    ) -> None:
        self._state_repository = state_repository
        self._cycle_callback = cycle_callback
        self._lock = threading.Lock()
        self._last_tick_at: datetime | None = None
        self._last_action: str | None = None
        self._last_error: str | None = None

    def tick(
        self,
        *,
        now: datetime | None = None,
        force: bool = False,
    ) -> dict[str, object]:
        tick_time = now or datetime.now(
            timezone.utc
        )
        self._last_tick_at = tick_time

        if not self._lock.acquire(
            blocking=False
        ):
            self._last_action = "SKIPPED_BUSY"

            return {
                "action": "SKIPPED_BUSY",
                "reason": (
                    "A scheduler runner tick is "
                    "already in progress."
                ),
                "cycle": None,
                "state": self._serialize_state(),
            }

        try:
            state = (
                self._state_repository
                .get_or_create()
            )

            if not state.enabled and not force:
                self._last_action = (
                    "SKIPPED_DISABLED"
                )

                return {
                    "action": "SKIPPED_DISABLED",
                    "reason": (
                        "Scheduler is disabled."
                    ),
                    "cycle": None,
                    "state": self._serialize_state(
                        state
                    ),
                }

            if (
                not force
                and state.next_run_at is not None
                and self._as_utc(
                    state.next_run_at
                ) > tick_time
            ):
                self._last_action = (
                    "SKIPPED_NOT_DUE"
                )

                return {
                    "action": "SKIPPED_NOT_DUE",
                    "reason": (
                        "Scheduler next-run time "
                        "has not been reached."
                    ),
                    "cycle": None,
                    "state": self._serialize_state(
                        state
                    ),
                }

            try:
                cycle = self._cycle_callback()
            except Exception as exc:
                self._last_action = "FAILED"
                self._last_error = str(exc)

                updated = (
                    self._state_repository
                    .record_runner_failure(
                        occurred_at=tick_time,
                        disable_threshold=(
                            self
                            .FAILURE_DISABLE_THRESHOLD
                        ),
                    )
                )

                return {
                    "action": "FAILED",
                    "reason": str(exc),
                    "cycle": None,
                    "state": self._serialize_state(
                        updated
                    ),
                }

            if cycle is None:
                self._last_action = (
                    "SKIPPED_NO_PAYLOAD"
                )
                self._last_error = None

                updated = (
                    self._state_repository
                    .record_runner_skip(
                        occurred_at=tick_time
                    )
                )

                return {
                    "action": (
                        "SKIPPED_NO_PAYLOAD"
                    ),
                    "reason": (
                        "No scheduler payload is "
                        "configured."
                    ),
                    "cycle": None,
                    "state": self._serialize_state(
                        updated
                    ),
                }

            self._last_action = "EXECUTED"
            self._last_error = None

            return {
                "action": "EXECUTED",
                "reason": None,
                "cycle": cycle,
                "state": self._serialize_state(),
            }
        finally:
            self._lock.release()

    def status(self) -> SchedulerRunnerStatus:
        return SchedulerRunnerStatus(
            running=self._lock.locked(),
            last_tick_at=self._last_tick_at,
            last_action=self._last_action,
            last_error=self._last_error,
        )

    def _serialize_state(
        self,
        state: object | None = None,
    ) -> dict[str, object]:
        resolved = (
            state
            or self._state_repository
            .get_or_create()
        )

        return {
            "enabled": resolved.enabled,
            "interval_seconds": (
                resolved.interval_seconds
            ),
            "last_run_at": resolved.last_run_at,
            "next_run_at": resolved.next_run_at,
            "last_cycle_id": (
                resolved.last_cycle_id
            ),
            "consecutive_failures": (
                resolved.consecutive_failures
            ),
            "updated_at": resolved.updated_at,
        }

    @staticmethod
    def _as_utc(
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(timezone.utc)
