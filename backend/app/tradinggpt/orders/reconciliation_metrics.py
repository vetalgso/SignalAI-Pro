from __future__ import annotations

import math
from collections.abc import Callable
from datetime import datetime, timezone

from app.tradinggpt.scheduler.background_loop import (
    SchedulerBackgroundLoopStatus,
)


PROMETHEUS_CONTENT_TYPE = (
    "text/plain; version=0.0.4; charset=utf-8"
)


class OrderReconciliationMetricsService:
    def __init__(
        self,
        *,
        enabled: bool,
        batch_size: int,
        status_provider: Callable[
            [],
            SchedulerBackgroundLoopStatus,
        ],
        now_provider: Callable[
            [],
            datetime,
        ] | None = None,
    ) -> None:
        if batch_size <= 0:
            raise ValueError(
                "Reconciliation metrics batch size "
                "must be greater than zero."
            )

        self._enabled = enabled
        self._batch_size = batch_size
        self._status_provider = status_provider
        self._now_provider = (
            now_provider
            or (
                lambda: datetime.now(
                    timezone.utc
                )
            )
        )

    def render(self) -> str:
        status = self._status_provider()
        now = self._now_provider()

        started_timestamp = self._timestamp(
            status.last_tick_started_at
        )
        finished_timestamp = self._timestamp(
            status.last_tick_finished_at
        )

        duration_seconds = 0.0

        if (
            status.last_tick_started_at
            is not None
            and status.last_tick_finished_at
            is not None
        ):
            duration_seconds = max(
                (
                    status.last_tick_finished_at
                    - status.last_tick_started_at
                ).total_seconds(),
                0.0,
            )

        seconds_since_last_tick = 0.0

        if status.last_tick_finished_at is not None:
            seconds_since_last_tick = max(
                (
                    now
                    - status.last_tick_finished_at
                ).total_seconds(),
                0.0,
            )

        last_tick_failed = (
            status.last_error is not None
            or status.last_action
            in {
                "FAILED",
                "LOOP_ERROR",
            }
        )

        lines: list[str] = []

        self._append_metric(
            lines,
            name=(
                "signalai_order_reconciliation_enabled"
            ),
            metric_type="gauge",
            help_text=(
                "Whether automatic order "
                "reconciliation is enabled."
            ),
            value=self._enabled,
        )
        self._append_metric(
            lines,
            name=(
                "signalai_order_reconciliation_read_only"
            ),
            metric_type="gauge",
            help_text=(
                "Whether automatic reconciliation "
                "uses read-only exchange operations."
            ),
            value=True,
        )
        self._append_metric(
            lines,
            name=(
                "signalai_order_reconciliation_"
                "background_running"
            ),
            metric_type="gauge",
            help_text=(
                "Whether the reconciliation "
                "background loop is running."
            ),
            value=status.running,
        )
        self._append_metric(
            lines,
            name=(
                "signalai_order_reconciliation_"
                "background_stopping"
            ),
            metric_type="gauge",
            help_text=(
                "Whether the reconciliation "
                "background loop is stopping."
            ),
            value=status.stopping,
        )
        self._append_metric(
            lines,
            name=(
                "signalai_order_reconciliation_"
                "iterations_total"
            ),
            metric_type="counter",
            help_text=(
                "Total reconciliation background "
                "loop iterations."
            ),
            value=status.iterations,
        )
        self._append_metric(
            lines,
            name=(
                "signalai_order_reconciliation_"
                "failed_ticks_total"
            ),
            metric_type="counter",
            help_text=(
                "Total failed reconciliation "
                "background ticks."
            ),
            value=status.failed_ticks,
        )
        self._append_metric(
            lines,
            name=(
                "signalai_order_reconciliation_"
                "poll_interval_seconds"
            ),
            metric_type="gauge",
            help_text=(
                "Configured reconciliation "
                "poll interval in seconds."
            ),
            value=status.poll_interval_seconds,
        )
        self._append_metric(
            lines,
            name=(
                "signalai_order_reconciliation_"
                "batch_size"
            ),
            metric_type="gauge",
            help_text=(
                "Configured maximum reconciliation "
                "batch size."
            ),
            value=self._batch_size,
        )
        self._append_metric(
            lines,
            name=(
                "signalai_order_reconciliation_"
                "last_tick_observed"
            ),
            metric_type="gauge",
            help_text=(
                "Whether at least one reconciliation "
                "tick has completed."
            ),
            value=(
                status.last_tick_finished_at
                is not None
            ),
        )
        self._append_metric(
            lines,
            name=(
                "signalai_order_reconciliation_"
                "last_tick_started_timestamp_seconds"
            ),
            metric_type="gauge",
            help_text=(
                "Unix timestamp when the latest "
                "reconciliation tick started."
            ),
            value=started_timestamp,
        )
        self._append_metric(
            lines,
            name=(
                "signalai_order_reconciliation_"
                "last_tick_finished_timestamp_seconds"
            ),
            metric_type="gauge",
            help_text=(
                "Unix timestamp when the latest "
                "reconciliation tick finished."
            ),
            value=finished_timestamp,
        )
        self._append_metric(
            lines,
            name=(
                "signalai_order_reconciliation_"
                "last_tick_duration_seconds"
            ),
            metric_type="gauge",
            help_text=(
                "Duration of the latest "
                "reconciliation tick."
            ),
            value=duration_seconds,
        )
        self._append_metric(
            lines,
            name=(
                "signalai_order_reconciliation_"
                "seconds_since_last_tick"
            ),
            metric_type="gauge",
            help_text=(
                "Seconds since the latest "
                "reconciliation tick finished."
            ),
            value=seconds_since_last_tick,
        )
        self._append_metric(
            lines,
            name=(
                "signalai_order_reconciliation_"
                "last_tick_failed"
            ),
            metric_type="gauge",
            help_text=(
                "Whether the latest reconciliation "
                "tick failed."
            ),
            value=last_tick_failed,
        )

        action = self._escape_label(
            status.last_action or "NONE"
        )

        lines.extend(
            [
                (
                    "# HELP "
                    "signalai_order_reconciliation_"
                    "last_action_info "
                    "Latest reconciliation action."
                ),
                (
                    "# TYPE "
                    "signalai_order_reconciliation_"
                    "last_action_info gauge"
                ),
                (
                    "signalai_order_reconciliation_"
                    f'last_action_info{{action="{action}"}} 1'
                ),
            ]
        )

        return "\n".join(lines) + "\n"

    @staticmethod
    def _timestamp(
        value: datetime | None,
    ) -> float:
        if value is None:
            return 0.0

        return value.timestamp()

    @classmethod
    def _append_metric(
        cls,
        lines: list[str],
        *,
        name: str,
        metric_type: str,
        help_text: str,
        value: bool | int | float,
    ) -> None:
        lines.extend(
            [
                f"# HELP {name} {help_text}",
                f"# TYPE {name} {metric_type}",
                (
                    f"{name} "
                    f"{cls._format_value(value)}"
                ),
            ]
        )

    @staticmethod
    def _format_value(
        value: bool | int | float,
    ) -> str:
        if isinstance(value, bool):
            return "1" if value else "0"

        if isinstance(value, int):
            return str(value)

        if not math.isfinite(value):
            return "0"

        return format(value, ".15g")

    @staticmethod
    def _escape_label(value: str) -> str:
        return (
            value
            .replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace('"', '\\"')
        )
