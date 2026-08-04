#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import UTC, datetime
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from pathlib import Path
from typing import Any


PROMETHEUS_CONTENT_TYPE = (
    "text/plain; version=0.0.4; charset=utf-8"
)

DEFAULT_REPORT_FILE = Path(
    os.environ.get(
        "SIGNALAI_E2E_REPORT_FILE",
        "/data/latest.json",
    )
)

DEFAULT_HISTORY_FILE = Path(
    os.environ.get(
        "SIGNALAI_E2E_HISTORY_FILE",
        "/data/history.json",
    )
)

DEFAULT_STATE_FILE = Path(
    os.environ.get(
        "SIGNALAI_E2E_RUNNER_STATE_FILE",
        "/data/runner-state.json",
    )
)

RUN_STATUSES = (
    "SUCCESS",
    "FAILURE",
)

RUNNER_STATUSES = (
    "STARTING",
    "WAITING",
    "RUNNING",
    "COMPLETED",
    "STOPPED",
)

RUNNER_RESULTS = (
    "NONE",
    "SUCCESS",
    "FAILURE",
    "LOCKED",
)


def format_number(value: float | int) -> str:
    number = float(value)

    if not math.isfinite(number):
        return "0"

    if number.is_integer():
        return str(int(number))

    return format(number, ".15g")


def escape_label(value: object) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


def append_metric(
    lines: list[str],
    *,
    name: str,
    help_text: str,
    value: float | int,
) -> None:
    lines.extend(
        (
            f"# HELP {name} {help_text}",
            f"# TYPE {name} gauge",
            f"{name} {format_number(value)}",
        )
    )


def append_labeled_metric(
    lines: list[str],
    *,
    name: str,
    help_text: str,
    samples: list[
        tuple[dict[str, object], float | int]
    ],
) -> None:
    lines.extend(
        (
            f"# HELP {name} {help_text}",
            f"# TYPE {name} gauge",
        )
    )

    for labels, value in samples:
        rendered_labels = ",".join(
            f'{key}="{escape_label(labels[key])}"'
            for key in sorted(labels)
        )

        lines.append(
            f"{name}{{{rendered_labels}}} "
            f"{format_number(value)}"
        )


def read_json(
    path: Path,
    expected_type: type,
) -> tuple[bool, bool, Any]:
    if not path.exists():
        return False, False, None

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8")
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ):
        return True, False, None

    if not isinstance(payload, expected_type):
        return True, False, None

    return True, True, payload


def parse_timestamp(value: object) -> float:
    if not isinstance(value, str):
        return 0.0

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
        return 0.0

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC).timestamp()


def safe_number(
    value: object,
    *,
    default: float = 0.0,
) -> float:
    if isinstance(value, bool):
        return float(value)

    if not isinstance(value, (int, float)):
        return default

    number = float(value)

    return (
        number
        if math.isfinite(number)
        else default
    )


def render_metrics(
    *,
    report_file: Path,
    history_file: Path,
    state_file: Path = DEFAULT_STATE_FILE,
    now_timestamp: float | None = None,
) -> str:
    now = (
        time.time()
        if now_timestamp is None
        else float(now_timestamp)
    )

    (
        report_present,
        report_valid,
        report,
    ) = read_json(
        report_file,
        dict,
    )

    (
        history_present,
        history_valid,
        history,
    ) = read_json(
        history_file,
        list,
    )

    (
        state_present,
        state_valid,
        state,
    ) = read_json(
        state_file,
        dict,
    )

    report_data = (
        report
        if report_valid
        else {}
    )

    history_data = (
        history
        if history_valid
        else []
    )

    runner_data = (
        state
        if state_valid
        else {}
    )

    runner_status = str(
        runner_data.get(
            "runner_status",
            "",
        )
    ).upper()

    raw_last_result = (
        runner_data.get("last_result")
    )

    runner_last_result = (
        "NONE"
        if raw_last_result is None
        else str(raw_last_result).upper()
    )

    runner_updated_timestamp = (
        parse_timestamp(
            runner_data.get("updated_at")
        )
    )

    runner_state_age_seconds = (
        max(
            0.0,
            now - runner_updated_timestamp,
        )
        if runner_updated_timestamp > 0
        else 0.0
    )

    runner_next_timestamp = (
        parse_timestamp(
            runner_data.get("next_run_at")
        )
    )

    runner_next_delay_seconds = (
        max(
            0.0,
            runner_next_timestamp - now,
        )
        if runner_next_timestamp > 0
        else 0.0
    )

    runner_last_started_timestamp = (
        parse_timestamp(
            runner_data.get(
                "last_run_started_at"
            )
        )
    )

    runner_last_finished_timestamp = (
        parse_timestamp(
            runner_data.get(
                "last_run_finished_at"
            )
        )
    )

    runner_configuration = (
        runner_data.get("configuration")
    )

    runner_config = (
        runner_configuration
        if isinstance(
            runner_configuration,
            dict,
        )
        else {}
    )

    status = str(
        report_data.get("status", "")
    ).upper()

    finished_timestamp = parse_timestamp(
        report_data.get("finished_at")
    )

    age_seconds = (
        max(0.0, now - finished_timestamp)
        if finished_timestamp > 0
        else 0.0
    )

    telegram = report_data.get("telegram")

    telegram_data = (
        telegram
        if isinstance(telegram, dict)
        else {}
    )

    history_counts = {
        run_status: 0
        for run_status in RUN_STATUSES
    }

    for item in history_data:
        if not isinstance(item, dict):
            continue

        item_status = str(
            item.get("status", "")
        ).upper()

        if item_status in history_counts:
            history_counts[item_status] += 1

    lines: list[str] = []

    append_metric(
        lines,
        name="signalai_e2e_exporter_ready",
        help_text=(
            "Whether the E2E metrics exporter "
            "successfully rendered this scrape."
        ),
        value=1,
    )

    append_metric(
        lines,
        name="signalai_e2e_report_present",
        help_text=(
            "Whether the latest E2E JSON report "
            "file exists."
        ),
        value=int(report_present),
    )

    append_metric(
        lines,
        name="signalai_e2e_report_valid",
        help_text=(
            "Whether the latest E2E JSON report "
            "is valid."
        ),
        value=int(report_valid),
    )

    append_labeled_metric(
        lines,
        name="signalai_e2e_last_run_status",
        help_text=(
            "Latest E2E run status as a "
            "one-hot gauge."
        ),
        samples=[
            (
                {"status": run_status},
                int(
                    report_valid
                    and status == run_status
                ),
            )
            for run_status in RUN_STATUSES
        ],
    )

    append_metric(
        lines,
        name=(
            "signalai_e2e_last_run_"
            "finished_timestamp_seconds"
        ),
        help_text=(
            "Unix timestamp when the latest "
            "E2E run finished."
        ),
        value=finished_timestamp,
    )

    append_metric(
        lines,
        name=(
            "signalai_e2e_last_run_"
            "age_seconds"
        ),
        help_text=(
            "Seconds elapsed since the latest "
            "E2E run finished."
        ),
        value=age_seconds,
    )

    append_metric(
        lines,
        name=(
            "signalai_e2e_last_run_"
            "duration_seconds"
        ),
        help_text=(
            "Duration of the latest E2E run."
        ),
        value=safe_number(
            report_data.get(
                "duration_seconds"
            )
        ),
    )

    append_metric(
        lines,
        name=(
            "signalai_e2e_last_run_"
            "timeout_seconds"
        ),
        help_text=(
            "Configured timeout of the latest "
            "E2E run."
        ),
        value=safe_number(
            report_data.get(
                "timeout_seconds"
            )
        ),
    )

    append_metric(
        lines,
        name=(
            "signalai_e2e_last_run_"
            "runtime_rule_removed"
        ),
        help_text=(
            "Whether the runtime Prometheus "
            "rule was removed after the run."
        ),
        value=int(
            report_data.get(
                "runtime_rule_removed"
            )
            is True
        ),
    )

    append_metric(
        lines,
        name=(
            "signalai_e2e_last_run_"
            "telegram_notifications"
        ),
        help_text=(
            "Alertmanager Telegram notification "
            "counter observed after the run."
        ),
        value=safe_number(
            telegram_data.get(
                "notifications_total"
            )
        ),
    )

    append_metric(
        lines,
        name=(
            "signalai_e2e_last_run_"
            "telegram_failures"
        ),
        help_text=(
            "Alertmanager Telegram failure "
            "counter observed after the run."
        ),
        value=safe_number(
            telegram_data.get(
                "failures_total"
            )
        ),
    )

    append_metric(
        lines,
        name="signalai_e2e_history_present",
        help_text=(
            "Whether the E2E history JSON "
            "file exists."
        ),
        value=int(history_present),
    )

    append_metric(
        lines,
        name="signalai_e2e_history_valid",
        help_text=(
            "Whether the E2E history JSON "
            "file is valid."
        ),
        value=int(history_valid),
    )

    append_metric(
        lines,
        name="signalai_e2e_history_entries",
        help_text=(
            "Number of entries in bounded "
            "E2E history."
        ),
        value=len(history_data),
    )

    append_labeled_metric(
        lines,
        name="signalai_e2e_history_runs",
        help_text=(
            "E2E history entries grouped "
            "by result status."
        ),
        samples=[
            (
                {"status": run_status},
                history_counts[run_status],
            )
            for run_status in RUN_STATUSES
        ],
    )

    append_metric(
        lines,
        name=(
            "signalai_e2e_runner_"
            "state_present"
        ),
        help_text=(
            "Whether the periodic E2E runner "
            "state file exists."
        ),
        value=int(state_present),
    )

    append_metric(
        lines,
        name=(
            "signalai_e2e_runner_"
            "state_valid"
        ),
        help_text=(
            "Whether the periodic E2E runner "
            "state file is valid."
        ),
        value=int(state_valid),
    )

    append_labeled_metric(
        lines,
        name="signalai_e2e_runner_status",
        help_text=(
            "Periodic E2E runner status as a "
            "bounded one-hot gauge."
        ),
        samples=[
            (
                {"status": item},
                int(
                    state_valid
                    and runner_status == item
                ),
            )
            for item in RUNNER_STATUSES
        ],
    )

    append_labeled_metric(
        lines,
        name=(
            "signalai_e2e_runner_"
            "last_result"
        ),
        help_text=(
            "Last periodic E2E runner result "
            "as a bounded one-hot gauge."
        ),
        samples=[
            (
                {"result": item},
                int(
                    state_valid
                    and runner_last_result
                    == item
                ),
            )
            for item in RUNNER_RESULTS
        ],
    )

    append_metric(
        lines,
        name=(
            "signalai_e2e_runner_"
            "updated_timestamp_seconds"
        ),
        help_text=(
            "Unix timestamp of the latest "
            "runner state update."
        ),
        value=runner_updated_timestamp,
    )

    append_metric(
        lines,
        name=(
            "signalai_e2e_runner_"
            "state_age_seconds"
        ),
        help_text=(
            "Seconds elapsed since the latest "
            "runner state update."
        ),
        value=runner_state_age_seconds,
    )

    append_metric(
        lines,
        name=(
            "signalai_e2e_runner_"
            "next_run_timestamp_seconds"
        ),
        help_text=(
            "Unix timestamp of the next "
            "scheduled periodic E2E run."
        ),
        value=runner_next_timestamp,
    )

    append_metric(
        lines,
        name=(
            "signalai_e2e_runner_"
            "next_run_delay_seconds"
        ),
        help_text=(
            "Seconds remaining until the next "
            "scheduled periodic E2E run."
        ),
        value=runner_next_delay_seconds,
    )

    append_metric(
        lines,
        name=(
            "signalai_e2e_runner_"
            "last_run_started_timestamp_seconds"
        ),
        help_text=(
            "Unix timestamp when the latest "
            "periodic E2E run started."
        ),
        value=runner_last_started_timestamp,
    )

    append_metric(
        lines,
        name=(
            "signalai_e2e_runner_"
            "last_run_finished_timestamp_seconds"
        ),
        help_text=(
            "Unix timestamp when the latest "
            "periodic E2E run finished."
        ),
        value=runner_last_finished_timestamp,
    )

    append_metric(
        lines,
        name=(
            "signalai_e2e_runner_"
            "last_duration_seconds"
        ),
        help_text=(
            "Duration of the latest periodic "
            "E2E runner invocation."
        ),
        value=safe_number(
            runner_data.get(
                "last_duration_seconds"
            )
        ),
    )

    append_metric(
        lines,
        name=(
            "signalai_e2e_runner_"
            "last_exit_code"
        ),
        help_text=(
            "Exit code of the latest periodic "
            "E2E runner invocation."
        ),
        value=safe_number(
            runner_data.get(
                "last_exit_code"
            )
        ),
    )

    for suffix, key, help_text in (
        (
            "runs_total",
            "runs_total",
            "Total periodic E2E invocations.",
        ),
        (
            "successes_total",
            "successes_total",
            "Successful periodic E2E runs.",
        ),
        (
            "failures_total",
            "failures_total",
            "Failed periodic E2E runs.",
        ),
        (
            "lock_conflicts_total",
            "lock_conflicts_total",
            "Periodic E2E lock conflicts.",
        ),
        (
            "consecutive_failures",
            "consecutive_failures",
            (
                "Current number of consecutive "
                "periodic E2E failures."
            ),
        ),
    ):
        append_metric(
            lines,
            name=(
                "signalai_e2e_runner_"
                + suffix
            ),
            help_text=help_text,
            value=safe_number(
                runner_data.get(key)
            ),
        )

    for suffix, key, help_text in (
        (
            "startup_delay_seconds",
            "startup_delay_seconds",
            "Configured runner startup delay.",
        ),
        (
            "interval_seconds",
            "interval_seconds",
            (
                "Configured delay after a "
                "successful periodic run."
            ),
        ),
        (
            "retry_delay_seconds",
            "retry_delay_seconds",
            (
                "Configured retry delay after "
                "failure or lock conflict."
            ),
        ),
        (
            "self_test_timeout_seconds",
            "self_test_timeout_seconds",
            (
                "Configured timeout for each "
                "E2E self-test phase."
            ),
        ),
        (
            "process_timeout_seconds",
            "process_timeout_seconds",
            (
                "Configured runner subprocess "
                "timeout."
            ),
        ),
        (
            "history_limit",
            "history_limit",
            (
                "Configured bounded E2E history "
                "size."
            ),
        ),
    ):
        append_metric(
            lines,
            name=(
                "signalai_e2e_runner_config_"
                + suffix
            ),
            help_text=help_text,
            value=safe_number(
                runner_config.get(key)
            ),
        )

    return "\n".join(lines) + "\n"


def build_handler(
    *,
    report_file: Path,
    history_file: Path,
    state_file: Path,
) -> type[BaseHTTPRequestHandler]:
    class MetricsHandler(
        BaseHTTPRequestHandler
    ):
        def do_GET(self) -> None:
            if self.path == "/metrics":
                payload = render_metrics(
                    report_file=report_file,
                    history_file=history_file,
                    state_file=state_file,
                ).encode("utf-8")

                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    PROMETHEUS_CONTENT_TYPE,
                )
                self.send_header(
                    "Content-Length",
                    str(len(payload)),
                )
                self.end_headers()
                self.wfile.write(payload)
                return

            if self.path == "/-/ready":
                payload = b"ready\n"

                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "text/plain; charset=utf-8",
                )
                self.send_header(
                    "Content-Length",
                    str(len(payload)),
                )
                self.end_headers()
                self.wfile.write(payload)
                return

            self.send_response(404)
            self.end_headers()

        def log_message(
            self,
            format: str,
            *args: object,
        ) -> None:
            return

    return MetricsHandler


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Expose SignalAI E2E JSON reports "
            "as Prometheus metrics."
        )
    )

    parser.add_argument(
        "--host",
        default="0.0.0.0",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=9102,
    )

    parser.add_argument(
        "--report-file",
        type=Path,
        default=DEFAULT_REPORT_FILE,
    )

    parser.add_argument(
        "--history-file",
        type=Path,
        default=DEFAULT_HISTORY_FILE,
    )

    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE_FILE,
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Render one metrics snapshot "
            "and exit."
        ),
    )

    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        parser.error(
            "--port must be between "
            "1 and 65535"
        )

    if args.check:
        print(
            render_metrics(
                report_file=args.report_file,
                history_file=args.history_file,
                state_file=args.state_file,
            ),
            end="",
        )
        return

    handler = build_handler(
        report_file=args.report_file,
        history_file=args.history_file,
        state_file=args.state_file,
    )

    server = ThreadingHTTPServer(
        (args.host, args.port),
        handler,
    )

    print(
        "SignalAI E2E exporter listening on "
        f"{args.host}:{args.port}",
        flush=True,
    )

    server.serve_forever()


if __name__ == "__main__":
    main()
