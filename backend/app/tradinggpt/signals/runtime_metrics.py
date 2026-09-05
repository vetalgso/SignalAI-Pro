from __future__ import annotations

import math
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.signal_discovery import (
    SignalScanRun,
)
from app.models.trading_signal import (
    TelegramSignalDelivery,
    TradingSignal,
)
from app.tradinggpt.scheduler.background_loop import (
    SchedulerBackgroundLoopStatus,
)


PROMETHEUS_CONTENT_TYPE = (
    "text/plain; version=0.0.4; charset=utf-8"
)

DELIVERY_TYPES = (
    "SIGNAL_CREATED",
    "SIGNAL_STATUS_CHANGED",
    "UNKNOWN",
)
DELIVERY_STATUSES = (
    "PENDING",
    "PROCESSING",
    "RETRY",
    "SENT",
    "SKIPPED",
    "FAILED",
    "UNKNOWN",
)
IN_FLIGHT_STATUSES = {
    "PENDING",
    "PROCESSING",
    "RETRY",
}
TRACKABLE_SIGNAL_STATUSES = {
    "ACTIVE",
    "ENTRY_REACHED",
    "TP1_REACHED",
    "TP2_REACHED",
}
ALLOWED_ACTIONS = {
    "NONE",
    "IDLE",
    "COMPLETED",
    "PARTIAL",
    "FAILED",
    "SKIPPED_DISABLED",
    "SKIPPED_LOCKED",
    "LOOP_ERROR",
}
SCANNER_ERROR_CODES = (
    "UPSTREAM_TIMEOUT",
    "UPSTREAM_CONNECTION_ERROR",
    "INVALID_ANALYSIS_PAYLOAD",
    "UNEXPECTED_ANALYSIS_ERROR",
    "UNKNOWN",
)


class SignalPipelineMetricsService:
    def __init__(
        self,
        *,
        session: Session,
        scanner_enabled: bool,
        telegram_enabled: bool,
        scanner_status_provider: Callable[
            [],
            SchedulerBackgroundLoopStatus,
        ],
        telegram_status_provider: Callable[
            [],
            SchedulerBackgroundLoopStatus,
        ],
        now_provider: Callable[
            [],
            datetime,
        ] | None = None,
    ) -> None:
        self._session = session
        self._scanner_enabled = (
            scanner_enabled
        )
        self._telegram_enabled = (
            telegram_enabled
        )
        self._scanner_status_provider = (
            scanner_status_provider
        )
        self._telegram_status_provider = (
            telegram_status_provider
        )
        self._now_provider = (
            now_provider
            or (
                lambda: datetime.now(
                    timezone.utc
                )
            )
        )

    def render(self) -> str:
        now = self._aware_utc(
            self._now_provider()
        )
        scanner_status = (
            self._scanner_status_provider()
        )
        telegram_status = (
            self._telegram_status_provider()
        )

        lines: list[str] = []

        self._append_loop_metrics(
            lines,
            prefix="signalai_signal_scanner",
            enabled=self._scanner_enabled,
            status=scanner_status,
            now=now,
        )
        self._append_loop_metrics(
            lines,
            prefix=(
                "signalai_telegram_signal_"
                "dispatcher"
            ),
            enabled=self._telegram_enabled,
            status=telegram_status,
            now=now,
        )

        (
            latest_run_observed,
            latest_run_failed_assets,
            latest_run_error_counts,
        ) = self._latest_scanner_errors()

        self._append_metric(
            lines,
            name=(
                "signalai_signal_scanner_"
                "latest_run_observed"
            ),
            metric_type="gauge",
            help_text=(
                "Whether a completed scanner run "
                "has been persisted."
            ),
            value=latest_run_observed,
        )
        self._append_metric(
            lines,
            name=(
                "signalai_signal_scanner_"
                "latest_run_failed_assets"
            ),
            metric_type="gauge",
            help_text=(
                "Failed asset analyses in the "
                "latest completed scanner run."
            ),
            value=latest_run_failed_assets,
        )

        lines.extend(
            [
                (
                    "# HELP "
                    "signalai_signal_scanner_"
                    "latest_run_errors "
                    "Errors in the latest completed "
                    "scanner run by bounded code."
                ),
                (
                    "# TYPE "
                    "signalai_signal_scanner_"
                    "latest_run_errors gauge"
                ),
            ]
        )

        for error_code in SCANNER_ERROR_CODES:
            value = latest_run_error_counts.get(
                error_code,
                0,
            )
            lines.append(
                (
                    "signalai_signal_scanner_"
                    "latest_run_errors"
                    f'{{error_code="{error_code}"}} '
                    f"{value}"
                )
            )

        counts = self._delivery_counts()

        lines.extend(
            [
                (
                    "# HELP "
                    "signalai_telegram_signal_"
                    "outbox_deliveries "
                    "Current Telegram signal "
                    "deliveries by type and status."
                ),
                (
                    "# TYPE "
                    "signalai_telegram_signal_"
                    "outbox_deliveries gauge"
                ),
            ]
        )

        for delivery_type in DELIVERY_TYPES:
            for delivery_status in (
                DELIVERY_STATUSES
            ):
                value = counts.get(
                    (
                        delivery_type,
                        delivery_status,
                    ),
                    0,
                )
                lines.append(
                    (
                        "signalai_telegram_signal_"
                        "outbox_deliveries"
                        f'{{delivery_type="'
                        f'{delivery_type}",'
                        f'status="{delivery_status}"'
                        f'}} {value}'
                    )
                )

        total = sum(counts.values())
        in_flight = sum(
            value
            for (
                _,
                delivery_status,
            ), value in counts.items()
            if (
                delivery_status
                in IN_FLIGHT_STATUSES
            )
        )
        failed = sum(
            value
            for (
                _,
                delivery_status,
            ), value in counts.items()
            if delivery_status == "FAILED"
        )

        self._append_metric(
            lines,
            name=(
                "signalai_telegram_signal_"
                "outbox_total"
            ),
            metric_type="gauge",
            help_text=(
                "Current total Telegram signal "
                "delivery rows."
            ),
            value=total,
        )
        self._append_metric(
            lines,
            name=(
                "signalai_telegram_signal_"
                "outbox_in_flight"
            ),
            metric_type="gauge",
            help_text=(
                "Current pending, processing, "
                "or retry deliveries."
            ),
            value=in_flight,
        )
        self._append_metric(
            lines,
            name=(
                "signalai_telegram_signal_"
                "outbox_failed"
            ),
            metric_type="gauge",
            help_text=(
                "Current failed Telegram signal "
                "deliveries."
            ),
            value=failed,
        )
        self._append_metric(
            lines,
            name=(
                "signalai_telegram_signal_"
                "outbox_oldest_in_flight_"
                "age_seconds"
            ),
            metric_type="gauge",
            help_text=(
                "Age of the oldest in-flight "
                "Telegram delivery."
            ),
            value=self._oldest_in_flight_age(
                now
            ),
        )
        self._append_metric(
            lines,
            name=(
                "signalai_trading_signals_"
                "trackable"
            ),
            metric_type="gauge",
            help_text=(
                "Current signals tracked for "
                "market lifecycle changes."
            ),
            value=self._trackable_signals(),
        )

        return "\n".join(lines) + "\n"

    def _latest_scanner_errors(
        self,
    ) -> tuple[
        bool,
        int,
        dict[str, int],
    ]:
        run = self._session.scalar(
            select(
                SignalScanRun
            )
            .where(
                SignalScanRun.status
                == "COMPLETED"
            )
            .order_by(
                SignalScanRun.id.desc()
            )
            .limit(1)
        )

        if run is None:
            return False, 0, {}

        counts: dict[str, int] = {}

        for raw_error in (
            run.scanner_errors or []
        ):
            if not isinstance(raw_error, dict):
                error_code = "UNKNOWN"
            else:
                raw_code = str(
                    raw_error.get(
                        "error_code",
                        "",
                    )
                ).upper()

                if raw_code in (
                    SCANNER_ERROR_CODES[:-1]
                ):
                    error_code = raw_code
                else:
                    error_code = (
                        self
                        ._legacy_scanner_error_code(
                            raw_error.get("error")
                        )
                    )

            counts[error_code] = (
                counts.get(error_code, 0)
                + 1
            )

        return (
            True,
            int(run.failed_assets),
            counts,
        )

    @staticmethod
    def _legacy_scanner_error_code(
        raw_error: object,
    ) -> str:
        error_name = str(raw_error or "")

        if error_name in {
            "TimeoutError",
            "ReadTimeout",
            "ConnectTimeout",
            "PoolTimeout",
        }:
            return "UPSTREAM_TIMEOUT"

        if error_name in {
            "ConnectionError",
            "ConnectError",
            "NetworkError",
            "RemoteProtocolError",
        }:
            return "UPSTREAM_CONNECTION_ERROR"

        if error_name in {
            "TypeError",
            "ValueError",
            "KeyError",
            "IndexError",
            "AttributeError",
        }:
            return "INVALID_ANALYSIS_PAYLOAD"

        return "UNKNOWN"

    def _delivery_counts(
        self,
    ) -> dict[tuple[str, str], int]:
        statement = (
            select(
                TelegramSignalDelivery
                .delivery_type,
                TelegramSignalDelivery.status,
                func.count(
                    TelegramSignalDelivery.id
                ),
            )
            .group_by(
                TelegramSignalDelivery
                .delivery_type,
                TelegramSignalDelivery.status,
            )
        )

        counts: dict[
            tuple[str, str],
            int,
        ] = {}

        for (
            raw_type,
            raw_status,
            total,
        ) in self._session.execute(
            statement
        ).all():
            delivery_type = str(
                raw_type
            ).upper()
            delivery_status = str(
                raw_status
            ).upper()

            if (
                delivery_type
                not in DELIVERY_TYPES[:-1]
            ):
                delivery_type = "UNKNOWN"

            if (
                delivery_status
                not in DELIVERY_STATUSES[:-1]
            ):
                delivery_status = "UNKNOWN"

            key = (
                delivery_type,
                delivery_status,
            )
            counts[key] = (
                counts.get(key, 0)
                + int(total)
            )

        return counts

    def _oldest_in_flight_age(
        self,
        now: datetime,
    ) -> float:
        oldest = self._session.scalar(
            select(
                func.min(
                    TelegramSignalDelivery
                    .created_at
                )
            ).where(
                TelegramSignalDelivery
                .status.in_(
                    IN_FLIGHT_STATUSES
                )
            )
        )

        if oldest is None:
            return 0.0

        return max(
            (
                now
                - self._aware_utc(oldest)
            ).total_seconds(),
            0.0,
        )

    def _trackable_signals(self) -> int:
        value = self._session.scalar(
            select(
                func.count(
                    TradingSignal.id
                )
            ).where(
                TradingSignal.status.in_(
                    TRACKABLE_SIGNAL_STATUSES
                )
            )
        )

        return int(value or 0)

    @classmethod
    def _append_loop_metrics(
        cls,
        lines: list[str],
        *,
        prefix: str,
        enabled: bool,
        status: SchedulerBackgroundLoopStatus,
        now: datetime,
    ) -> None:
        duration_seconds = 0.0

        if (
            status.last_tick_started_at
            is not None
            and status.last_tick_finished_at
            is not None
        ):
            duration_seconds = max(
                (
                    cls._aware_utc(
                        status
                        .last_tick_finished_at
                    )
                    - cls._aware_utc(
                        status
                        .last_tick_started_at
                    )
                ).total_seconds(),
                0.0,
            )

        seconds_since_last_tick = 0.0

        if (
            status.last_tick_finished_at
            is not None
        ):
            seconds_since_last_tick = max(
                (
                    now
                    - cls._aware_utc(
                        status
                        .last_tick_finished_at
                    )
                ).total_seconds(),
                0.0,
            )

        last_tick_failed = (
            status.last_error is not None
            or status.last_action
            in {
                "FAILED",
                "PARTIAL",
                "LOOP_ERROR",
            }
        )

        metrics = (
            (
                "enabled",
                "gauge",
                (
                    "Whether this signal pipeline "
                    "loop is enabled."
                ),
                enabled,
            ),
            (
                "background_running",
                "gauge",
                (
                    "Whether this signal pipeline "
                    "background loop is running."
                ),
                status.running,
            ),
            (
                "iterations_total",
                "counter",
                (
                    "Total background loop "
                    "iterations."
                ),
                status.iterations,
            ),
            (
                "failed_ticks_total",
                "counter",
                (
                    "Total failed background "
                    "loop ticks."
                ),
                status.failed_ticks,
            ),
            (
                "poll_interval_seconds",
                "gauge",
                (
                    "Configured loop interval "
                    "in seconds."
                ),
                status.poll_interval_seconds,
            ),
            (
                "last_tick_observed",
                "gauge",
                (
                    "Whether at least one loop "
                    "tick has finished."
                ),
                (
                    status.last_tick_finished_at
                    is not None
                ),
            ),
            (
                "seconds_since_last_tick",
                "gauge",
                (
                    "Seconds since the latest "
                    "loop tick finished."
                ),
                seconds_since_last_tick,
            ),
            (
                "last_tick_duration_seconds",
                "gauge",
                (
                    "Duration of the latest loop "
                    "tick in seconds."
                ),
                duration_seconds,
            ),
            (
                "last_tick_failed",
                "gauge",
                (
                    "Whether the latest loop "
                    "tick failed."
                ),
                last_tick_failed,
            ),
        )

        for (
            suffix,
            metric_type,
            help_text,
            value,
        ) in metrics:
            cls._append_metric(
                lines,
                name=f"{prefix}_{suffix}",
                metric_type=metric_type,
                help_text=help_text,
                value=value,
            )

        action = str(
            status.last_action or "NONE"
        ).upper()

        if action not in ALLOWED_ACTIONS:
            action = "UNKNOWN"

        lines.extend(
            [
                (
                    f"# HELP {prefix}_"
                    "last_action_info "
                    "Latest bounded loop action."
                ),
                (
                    f"# TYPE {prefix}_"
                    "last_action_info gauge"
                ),
                (
                    f"{prefix}_last_action_info"
                    f'{{action="{action}"}} 1'
                ),
            ]
        )

    @staticmethod
    def _aware_utc(
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(
            timezone.utc
        )

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
