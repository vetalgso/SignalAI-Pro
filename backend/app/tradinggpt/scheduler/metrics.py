from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any


PROMETHEUS_CONTENT_TYPE = (
    "text/plain; version=0.0.4"
)

_SCHEDULER_STATUSES = (
    "ACTIVE",
    "STANDBY",
    "DEGRADED",
)

_CYCLE_STATUSES = (
    "STARTED",
    "COMPLETED",
    "FAILED",
)

_CHECK_STATUSES = (
    "PASS",
    "WARN",
    "FAIL",
)


class SchedulerMetricsService:
    """
    Render scheduler runtime metrics using the
    Prometheus text exposition format 0.0.4.

    The service is read-only and does not mutate
    scheduler state or execute trading cycles.
    """

    def __init__(
        self,
        *,
        observability_provider: Callable[
            [],
            Mapping[str, object],
        ],
        readiness_provider: Callable[
            [],
            Mapping[str, object],
        ],
        cycle_counts_provider: Callable[
            [],
            Mapping[str, int],
        ],
    ) -> None:
        self._observability_provider = (
            observability_provider
        )
        self._readiness_provider = (
            readiness_provider
        )
        self._cycle_counts_provider = (
            cycle_counts_provider
        )

    def render(self) -> str:
        observability = dict(
            self._observability_provider()
        )
        readiness = dict(
            self._readiness_provider()
        )
        cycle_counts = {
            str(status).upper(): int(count)
            for status, count
            in self._cycle_counts_provider().items()
        }

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
        ready = bool(readiness.get("ready"))

        lines: list[str] = []

        self._single_metric(
            lines,
            name="signalai_scheduler_ready",
            help_text=(
                "Whether the scheduler runtime "
                "passes the readiness gate."
            ),
            metric_type="gauge",
            value=self._number(ready),
        )

        self._labeled_metric(
            lines,
            name="signalai_scheduler_status",
            help_text=(
                "Current scheduler runtime status "
                "as a one-hot gauge."
            ),
            metric_type="gauge",
            samples=[
                (
                    {"status": status},
                    self._number(
                        scheduler_status == status
                    ),
                )
                for status in _SCHEDULER_STATUSES
            ],
        )

        self._single_metric(
            lines,
            name="signalai_scheduler_enabled",
            help_text=(
                "Whether automatic scheduler "
                "execution is enabled."
            ),
            metric_type="gauge",
            value=self._number(
                bool(state.get("enabled"))
            ),
        )

        self._single_metric(
            lines,
            name=(
                "signalai_scheduler_"
                "payload_configured"
            ),
            help_text=(
                "Whether a persisted scheduler "
                "payload is configured."
            ),
            metric_type="gauge",
            value=self._number(
                bool(payload.get("configured"))
            ),
        )

        next_run_at = state.get("next_run_at")
        seconds_until_next_run = (
            observability.get(
                "seconds_until_next_run"
            )
        )

        self._single_metric(
            lines,
            name=(
                "signalai_scheduler_"
                "next_run_scheduled"
            ),
            help_text=(
                "Whether next_run_at is present."
            ),
            metric_type="gauge",
            value=self._number(
                next_run_at is not None
            ),
        )

        self._single_metric(
            lines,
            name=(
                "signalai_scheduler_next_run_due"
            ),
            help_text=(
                "Whether the next scheduler slot "
                "is currently due."
            ),
            metric_type="gauge",
            value=self._number(
                bool(
                    observability.get(
                        "next_run_due"
                    )
                )
            ),
        )

        self._single_metric(
            lines,
            name=(
                "signalai_scheduler_"
                "seconds_until_next_run"
            ),
            help_text=(
                "Seconds remaining until the next "
                "scheduled execution."
            ),
            metric_type="gauge",
            value=self._finite_number(
                seconds_until_next_run,
                default=0.0,
            ),
        )

        self._single_metric(
            lines,
            name=(
                "signalai_scheduler_"
                "consecutive_failures"
            ),
            help_text=(
                "Current number of consecutive "
                "scheduler cycle failures."
            ),
            metric_type="gauge",
            value=self._finite_number(
                state.get("consecutive_failures"),
                default=0.0,
            ),
        )

        self._background_metrics(
            lines=lines,
            background=background,
        )

        self._single_metric(
            lines,
            name=(
                "signalai_scheduler_"
                "distributed_lock_enabled"
            ),
            help_text=(
                "Whether distributed scheduler "
                "execution locking is enabled."
            ),
            metric_type="gauge",
            value=self._number(
                bool(
                    distributed_lock.get(
                        "enabled"
                    )
                )
            ),
        )

        self._readiness_metrics(
            lines=lines,
            readiness=readiness,
        )

        self._cycle_count_metrics(
            lines=lines,
            cycle_counts=cycle_counts,
        )

        self._last_cycle_metrics(
            lines=lines,
            last_cycle=observability.get(
                "last_cycle"
            ),
        )

        generated_at = self._as_datetime(
            observability.get("generated_at")
        )

        self._single_metric(
            lines,
            name=(
                "signalai_scheduler_"
                "metrics_generated_timestamp_seconds"
            ),
            help_text=(
                "Unix timestamp when this metrics "
                "snapshot was generated."
            ),
            metric_type="gauge",
            value=(
                generated_at.timestamp()
                if generated_at is not None
                else 0.0
            ),
        )

        return "\n".join(lines) + "\n"

    def _background_metrics(
        self,
        *,
        lines: list[str],
        background: Mapping[str, object],
    ) -> None:
        self._single_metric(
            lines,
            name=(
                "signalai_scheduler_"
                "background_running"
            ),
            help_text=(
                "Whether the scheduler background "
                "loop is running."
            ),
            metric_type="gauge",
            value=self._number(
                bool(background.get("running"))
            ),
        )

        self._single_metric(
            lines,
            name=(
                "signalai_scheduler_"
                "background_stopping"
            ),
            help_text=(
                "Whether the scheduler background "
                "loop is stopping."
            ),
            metric_type="gauge",
            value=self._number(
                bool(background.get("stopping"))
            ),
        )

        self._single_metric(
            lines,
            name=(
                "signalai_scheduler_"
                "background_iterations_total"
            ),
            help_text=(
                "Total background loop iterations "
                "since process startup."
            ),
            metric_type="counter",
            value=self._finite_number(
                background.get("iterations"),
                default=0.0,
            ),
        )

        self._single_metric(
            lines,
            name=(
                "signalai_scheduler_"
                "background_failed_ticks_total"
            ),
            help_text=(
                "Total failed background ticks "
                "since process startup."
            ),
            metric_type="counter",
            value=self._finite_number(
                background.get("failed_ticks"),
                default=0.0,
            ),
        )

        last_tick = self._as_datetime(
            background.get(
                "last_tick_finished_at"
            )
        )

        self._single_metric(
            lines,
            name=(
                "signalai_scheduler_background_"
                "last_tick_timestamp_seconds"
            ),
            help_text=(
                "Unix timestamp of the most recent "
                "completed background tick."
            ),
            metric_type="gauge",
            value=(
                last_tick.timestamp()
                if last_tick is not None
                else 0.0
            ),
        )

    def _readiness_metrics(
        self,
        *,
        lines: list[str],
        readiness: Mapping[str, object],
    ) -> None:
        raw_checks = readiness.get("checks")
        checks = (
            raw_checks
            if isinstance(raw_checks, list)
            else []
        )

        check_counts = {
            status: 0
            for status in _CHECK_STATUSES
        }

        for raw_check in checks:
            if not isinstance(
                raw_check,
                Mapping,
            ):
                continue

            check_status = raw_check.get(
                "status"
            )

            if check_status in check_counts:
                check_counts[
                    str(check_status)
                ] += 1

        self._labeled_metric(
            lines,
            name=(
                "signalai_scheduler_"
                "readiness_checks"
            ),
            help_text=(
                "Number of scheduler readiness "
                "checks by result status."
            ),
            metric_type="gauge",
            samples=[
                (
                    {"status": status},
                    check_counts[status],
                )
                for status in _CHECK_STATUSES
            ],
        )

        reason_codes = readiness.get(
            "reason_codes"
        )
        warning_codes = readiness.get(
            "warning_codes"
        )

        self._code_metrics(
            lines=lines,
            metric_name=(
                "signalai_scheduler_"
                "readiness_failure"
            ),
            help_text=(
                "Active scheduler readiness "
                "failure codes."
            ),
            codes=reason_codes,
        )

        self._code_metrics(
            lines=lines,
            metric_name=(
                "signalai_scheduler_"
                "readiness_warning"
            ),
            help_text=(
                "Active scheduler readiness "
                "warning codes."
            ),
            codes=warning_codes,
        )

    def _cycle_count_metrics(
        self,
        *,
        lines: list[str],
        cycle_counts: Mapping[str, int],
    ) -> None:
        statuses = sorted(
            set(_CYCLE_STATUSES)
            | set(cycle_counts)
        )

        self._labeled_metric(
            lines,
            name="signalai_scheduler_cycles_total",
            help_text=(
                "Persisted scheduler cycles by "
                "terminal or current status."
            ),
            metric_type="counter",
            samples=[
                (
                    {"status": status},
                    max(
                        0,
                        int(
                            cycle_counts.get(
                                status,
                                0,
                            )
                        ),
                    ),
                )
                for status in statuses
            ],
        )

    def _last_cycle_metrics(
        self,
        *,
        lines: list[str],
        last_cycle: Any,
    ) -> None:
        cycle = (
            last_cycle
            if isinstance(last_cycle, Mapping)
            else None
        )

        self._single_metric(
            lines,
            name=(
                "signalai_scheduler_"
                "last_cycle_present"
            ),
            help_text=(
                "Whether a scheduler cycle has "
                "been persisted."
            ),
            metric_type="gauge",
            value=self._number(
                cycle is not None
            ),
        )

        cycle_status = (
            str(cycle.get("status")).upper()
            if cycle is not None
            and cycle.get("status") is not None
            else ""
        )

        statuses = sorted(
            set(_CYCLE_STATUSES)
            | (
                {cycle_status}
                if cycle_status
                else set()
            )
        )

        self._labeled_metric(
            lines,
            name=(
                "signalai_scheduler_"
                "last_cycle_status"
            ),
            help_text=(
                "Latest scheduler cycle status "
                "as a one-hot gauge."
            ),
            metric_type="gauge",
            samples=[
                (
                    {"status": status},
                    self._number(
                        cycle_status == status
                    ),
                )
                for status in statuses
            ],
        )

        started_at = (
            self._as_datetime(
                cycle.get("started_at")
            )
            if cycle is not None
            else None
        )
        finished_at = (
            self._as_datetime(
                cycle.get("finished_at")
            )
            if cycle is not None
            else None
        )

        duration = 0.0

        if (
            started_at is not None
            and finished_at is not None
        ):
            duration = max(
                0.0,
                (
                    finished_at - started_at
                ).total_seconds(),
            )

        self._single_metric(
            lines,
            name=(
                "signalai_scheduler_"
                "last_cycle_duration_seconds"
            ),
            help_text=(
                "Duration of the latest scheduler "
                "cycle in seconds."
            ),
            metric_type="gauge",
            value=duration,
        )

        self._single_metric(
            lines,
            name=(
                "signalai_scheduler_last_cycle_"
                "finished_timestamp_seconds"
            ),
            help_text=(
                "Unix timestamp when the latest "
                "scheduler cycle finished."
            ),
            metric_type="gauge",
            value=(
                finished_at.timestamp()
                if finished_at is not None
                else 0.0
            ),
        )

        self._single_metric(
            lines,
            name=(
                "signalai_scheduler_"
                "last_cycle_failed"
            ),
            help_text=(
                "Whether the latest scheduler "
                "cycle failed."
            ),
            metric_type="gauge",
            value=self._number(
                cycle_status == "FAILED"
            ),
        )

        self._single_metric(
            lines,
            name=(
                "signalai_scheduler_"
                "last_cycle_simulated"
            ),
            help_text=(
                "Whether the latest scheduler "
                "execution was simulated."
            ),
            metric_type="gauge",
            value=self._number(
                bool(cycle.get("simulated"))
                if cycle is not None
                else False
            ),
        )

        self._single_metric(
            lines,
            name=(
                "signalai_scheduler_"
                "last_cycle_replayed"
            ),
            help_text=(
                "Whether the latest scheduler "
                "execution replayed an existing "
                "idempotent result."
            ),
            metric_type="gauge",
            value=self._number(
                bool(cycle.get("replayed"))
                if cycle is not None
                else False
            ),
        )

    def _code_metrics(
        self,
        *,
        lines: list[str],
        metric_name: str,
        help_text: str,
        codes: Any,
    ) -> None:
        normalized = sorted(
            {
                str(code)
                for code in codes
            }
            if isinstance(codes, list)
            else set()
        )

        self._labeled_metric(
            lines,
            name=metric_name,
            help_text=help_text,
            metric_type="gauge",
            samples=[
                (
                    {"code": code},
                    1,
                )
                for code in normalized
            ],
        )

    @classmethod
    def _single_metric(
        cls,
        lines: list[str],
        *,
        name: str,
        help_text: str,
        metric_type: str,
        value: int | float,
    ) -> None:
        lines.extend(
            (
                f"# HELP {name} {help_text}",
                f"# TYPE {name} {metric_type}",
                f"{name} {cls._format_number(value)}",
            )
        )

    @classmethod
    def _labeled_metric(
        cls,
        lines: list[str],
        *,
        name: str,
        help_text: str,
        metric_type: str,
        samples: list[
            tuple[
                Mapping[str, object],
                int | float,
            ]
        ],
    ) -> None:
        lines.extend(
            (
                f"# HELP {name} {help_text}",
                f"# TYPE {name} {metric_type}",
            )
        )

        for labels, value in samples:
            rendered_labels = ",".join(
                (
                    f'{key}="'
                    f'{cls._escape_label(value_)}'
                    f'"'
                )
                for key, value_
                in sorted(labels.items())
            )

            lines.append(
                f"{name}"
                f"{{{rendered_labels}}} "
                f"{cls._format_number(value)}"
            )

    @staticmethod
    def _escape_label(
        value: object,
    ) -> str:
        return (
            str(value)
            .replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace('"', '\\"')
        )

    @staticmethod
    def _format_number(
        value: int | float,
    ) -> str:
        number = float(value)

        if not math.isfinite(number):
            return "0"

        if number.is_integer():
            return str(int(number))

        return format(number, ".15g")

    @staticmethod
    def _number(
        value: bool,
    ) -> int:
        return 1 if value else 0

    @staticmethod
    def _finite_number(
        value: Any,
        *,
        default: float,
    ) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return default

        return (
            result
            if math.isfinite(result)
            else default
        )

    @staticmethod
    def _mapping(
        value: Any,
        *,
        name: str,
    ) -> Mapping[str, object]:
        if not isinstance(value, Mapping):
            raise TypeError(
                "Scheduler metrics "
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
                "Scheduler metrics "
                f"{name} must be a string."
            )

        return value

    @staticmethod
    def _as_datetime(
        value: Any,
    ) -> datetime | None:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            normalized = (
                value[:-1] + "+00:00"
                if value.endswith("Z")
                else value
            )

            try:
                parsed = datetime.fromisoformat(
                    normalized
                )
            except ValueError:
                return None
        else:
            return None

        if parsed.tzinfo is None:
            return parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(timezone.utc)
