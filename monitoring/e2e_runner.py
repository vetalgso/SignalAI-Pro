#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable


STATE_SCHEMA_VERSION = 1
LOCK_CONFLICT_EXIT_CODE = 75
PROCESS_TIMEOUT_EXIT_CODE = 124
PROCESS_START_ERROR_EXIT_CODE = 127

DEFAULT_SELF_TEST = (
    Path(__file__).resolve().parent
    / "e2e_self_test.py"
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


@dataclass(frozen=True)
class RunnerSettings:
    self_test: Path
    report_file: Path
    history_file: Path
    state_file: Path
    startup_delay_seconds: float
    interval_seconds: float
    retry_delay_seconds: float
    self_test_timeout_seconds: float
    process_timeout_seconds: float
    history_limit: int
    once: bool = False


CommandRunner = Callable[
    ...,
    subprocess.CompletedProcess[Any],
]

NowProvider = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


def format_argument(value: float) -> str:
    return (
        str(int(value))
        if value.is_integer()
        else str(value)
    )


def atomic_write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.tmp"
    )

    temporary.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    os.replace(
        temporary,
        path,
    )


def build_self_test_command(
    settings: RunnerSettings,
) -> list[str]:
    return [
        sys.executable,
        str(settings.self_test),
        "--timeout",
        format_argument(
            settings.self_test_timeout_seconds
        ),
        "--report-file",
        str(settings.report_file),
        "--history-file",
        str(settings.history_file),
        "--history-limit",
        str(settings.history_limit),
    ]


def settings_snapshot(
    settings: RunnerSettings,
) -> dict[str, Any]:
    return {
        "self_test": str(settings.self_test),
        "report_file": str(
            settings.report_file
        ),
        "history_file": str(
            settings.history_file
        ),
        "state_file": str(
            settings.state_file
        ),
        "startup_delay_seconds": (
            settings.startup_delay_seconds
        ),
        "interval_seconds": (
            settings.interval_seconds
        ),
        "retry_delay_seconds": (
            settings.retry_delay_seconds
        ),
        "self_test_timeout_seconds": (
            settings.self_test_timeout_seconds
        ),
        "process_timeout_seconds": (
            settings.process_timeout_seconds
        ),
        "history_limit": (
            settings.history_limit
        ),
        "once": settings.once,
    }


def initial_state(
    settings: RunnerSettings,
    *,
    now: datetime,
) -> dict[str, Any]:
    return {
        "schema_version": (
            STATE_SCHEMA_VERSION
        ),
        "runner_status": "STARTING",
        "last_result": None,
        "started_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "next_run_at": None,
        "last_run_started_at": None,
        "last_run_finished_at": None,
        "last_duration_seconds": None,
        "last_exit_code": None,
        "last_error": None,
        "runs_total": 0,
        "successes_total": 0,
        "failures_total": 0,
        "lock_conflicts_total": 0,
        "consecutive_failures": 0,
        "configuration": settings_snapshot(
            settings
        ),
    }


def execute_self_test(
    settings: RunnerSettings,
    *,
    command_runner: CommandRunner = (
        subprocess.run
    ),
) -> tuple[int, dict[str, str] | None]:
    command = build_self_test_command(
        settings
    )

    try:
        completed = command_runner(
            command,
            check=False,
            timeout=(
                settings
                .process_timeout_seconds
            ),
        )
    except subprocess.TimeoutExpired as error:
        return (
            PROCESS_TIMEOUT_EXIT_CODE,
            {
                "type": (
                    type(error).__name__
                ),
                "message": (
                    "E2E self-test process "
                    "exceeded runner timeout."
                ),
            },
        )
    except OSError as error:
        return (
            PROCESS_START_ERROR_EXIT_CODE,
            {
                "type": (
                    type(error).__name__
                ),
                "message": str(error),
            },
        )

    return int(completed.returncode), None


def classify_result(
    exit_code: int,
) -> str:
    if exit_code == 0:
        return "SUCCESS"

    if exit_code == LOCK_CONFLICT_EXIT_CODE:
        return "LOCKED"

    return "FAILURE"


def result_delay(
    settings: RunnerSettings,
    *,
    result: str,
) -> float:
    if result == "SUCCESS":
        return settings.interval_seconds

    return settings.retry_delay_seconds


def run_once(
    settings: RunnerSettings,
    state: dict[str, Any],
    *,
    schedule_next: bool,
    command_runner: CommandRunner = (
        subprocess.run
    ),
    now_provider: NowProvider = utc_now,
) -> tuple[int, float]:
    started_at = now_provider()
    started_monotonic = time.monotonic()

    state.update(
        {
            "runner_status": "RUNNING",
            "updated_at": (
                started_at.isoformat()
            ),
            "next_run_at": None,
            "last_run_started_at": (
                started_at.isoformat()
            ),
            "last_error": None,
        }
    )

    atomic_write_json(
        settings.state_file,
        state,
    )

    exit_code, process_error = (
        execute_self_test(
            settings,
            command_runner=command_runner,
        )
    )

    finished_at = now_provider()
    duration = max(
        0.0,
        time.monotonic()
        - started_monotonic,
    )

    result = classify_result(
        exit_code
    )

    state["runs_total"] = (
        int(state["runs_total"]) + 1
    )

    if result == "SUCCESS":
        state["successes_total"] = (
            int(
                state["successes_total"]
            )
            + 1
        )
        state["consecutive_failures"] = 0
    elif result == "LOCKED":
        state["lock_conflicts_total"] = (
            int(
                state[
                    "lock_conflicts_total"
                ]
            )
            + 1
        )
    else:
        state["failures_total"] = (
            int(state["failures_total"])
            + 1
        )
        state["consecutive_failures"] = (
            int(
                state[
                    "consecutive_failures"
                ]
            )
            + 1
        )

    delay = result_delay(
        settings,
        result=result,
    )

    next_run_at = (
        finished_at
        + timedelta(seconds=delay)
        if schedule_next
        else None
    )

    state.update(
        {
            "runner_status": (
                "WAITING"
                if schedule_next
                else "COMPLETED"
            ),
            "last_result": result,
            "updated_at": (
                finished_at.isoformat()
            ),
            "next_run_at": (
                next_run_at.isoformat()
                if next_run_at
                else None
            ),
            "last_run_finished_at": (
                finished_at.isoformat()
            ),
            "last_duration_seconds": (
                round(duration, 3)
            ),
            "last_exit_code": exit_code,
            "last_error": process_error,
        }
    )

    atomic_write_json(
        settings.state_file,
        state,
    )

    print(
        "Periodic E2E run result:",
        result,
        flush=True,
    )
    print(
        "Periodic E2E exit code:",
        exit_code,
        flush=True,
    )

    if schedule_next:
        print(
            "Next periodic E2E run:",
            state["next_run_at"],
            flush=True,
        )

    return exit_code, delay


def mark_stopped(
    settings: RunnerSettings,
    state: dict[str, Any],
    *,
    now_provider: NowProvider = utc_now,
) -> None:
    stopped_at = now_provider()

    state.update(
        {
            "runner_status": "STOPPED",
            "updated_at": (
                stopped_at.isoformat()
            ),
            "next_run_at": None,
        }
    )

    atomic_write_json(
        settings.state_file,
        state,
    )


def run_loop(
    settings: RunnerSettings,
    *,
    stop_event: threading.Event,
    command_runner: CommandRunner = (
        subprocess.run
    ),
    now_provider: NowProvider = utc_now,
) -> int:
    started_at = now_provider()

    state = initial_state(
        settings,
        now=started_at,
    )

    first_run_at = (
        started_at
        + timedelta(
            seconds=(
                settings
                .startup_delay_seconds
            )
        )
    )

    state.update(
        {
            "runner_status": "WAITING",
            "updated_at": (
                started_at.isoformat()
            ),
            "next_run_at": (
                first_run_at.isoformat()
            ),
        }
    )

    atomic_write_json(
        settings.state_file,
        state,
    )

    print(
        "Periodic E2E runner started.",
        flush=True,
    )
    print(
        "First periodic E2E run:",
        state["next_run_at"],
        flush=True,
    )

    if stop_event.wait(
        settings.startup_delay_seconds
    ):
        mark_stopped(
            settings,
            state,
            now_provider=now_provider,
        )
        return 0

    while not stop_event.is_set():
        exit_code, delay = run_once(
            settings,
            state,
            schedule_next=(
                not settings.once
            ),
            command_runner=(
                command_runner
            ),
            now_provider=now_provider,
        )

        if settings.once:
            return exit_code

        if stop_event.wait(delay):
            break

    mark_stopped(
        settings,
        state,
        now_provider=now_provider,
    )

    return 0


def environment_float(
    name: str,
    default: float,
) -> float:
    return float(
        os.environ.get(
            name,
            str(default),
        )
    )


def environment_int(
    name: str,
    default: int,
) -> int:
    return int(
        os.environ.get(
            name,
            str(default),
        )
    )


def parse_args() -> RunnerSettings:
    parser = argparse.ArgumentParser(
        description=(
            "Run the SignalAI monitoring "
            "E2E self-test periodically."
        )
    )

    parser.add_argument(
        "--self-test",
        type=Path,
        default=DEFAULT_SELF_TEST,
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
        "--startup-delay",
        type=float,
        default=environment_float(
            "E2E_RUNNER_STARTUP_DELAY_SECONDS",
            300,
        ),
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=environment_float(
            "E2E_RUNNER_INTERVAL_SECONDS",
            86400,
        ),
    )

    parser.add_argument(
        "--retry-delay",
        type=float,
        default=environment_float(
            "E2E_RUNNER_RETRY_DELAY_SECONDS",
            900,
        ),
    )

    parser.add_argument(
        "--self-test-timeout",
        type=float,
        default=environment_float(
            "E2E_RUNNER_SELF_TEST_TIMEOUT_SECONDS",
            90,
        ),
    )

    parser.add_argument(
        "--process-timeout",
        type=float,
        default=environment_float(
            "E2E_RUNNER_PROCESS_TIMEOUT_SECONDS",
            600,
        ),
    )

    parser.add_argument(
        "--history-limit",
        type=int,
        default=environment_int(
            "E2E_RUNNER_HISTORY_LIMIT",
            20,
        ),
    )

    parser.add_argument(
        "--once",
        action="store_true",
    )

    args = parser.parse_args()

    if args.startup_delay < 0:
        parser.error(
            "--startup-delay must be "
            "zero or positive"
        )

    for name, value in (
        ("--interval", args.interval),
        (
            "--retry-delay",
            args.retry_delay,
        ),
        (
            "--self-test-timeout",
            args.self_test_timeout,
        ),
        (
            "--process-timeout",
            args.process_timeout,
        ),
    ):
        if value <= 0:
            parser.error(
                f"{name} must be positive"
            )

    if args.history_limit <= 0:
        parser.error(
            "--history-limit must be "
            "positive"
        )

    if not args.self_test.is_file():
        parser.error(
            "--self-test must point to "
            "an existing file"
        )

    resolved_paths = {
        args.report_file.resolve(),
        args.history_file.resolve(),
        args.state_file.resolve(),
    }

    if len(resolved_paths) != 3:
        parser.error(
            "--report-file, --history-file "
            "and --state-file must differ"
        )

    return RunnerSettings(
        self_test=args.self_test,
        report_file=args.report_file,
        history_file=args.history_file,
        state_file=args.state_file,
        startup_delay_seconds=(
            args.startup_delay
        ),
        interval_seconds=args.interval,
        retry_delay_seconds=(
            args.retry_delay
        ),
        self_test_timeout_seconds=(
            args.self_test_timeout
        ),
        process_timeout_seconds=(
            args.process_timeout
        ),
        history_limit=args.history_limit,
        once=args.once,
    )


def main() -> None:
    settings = parse_args()
    stop_event = threading.Event()

    def request_stop(
        signum: int,
        frame: object,
    ) -> None:
        del signum
        del frame

        print(
            "Periodic E2E runner stopping.",
            flush=True,
        )
        stop_event.set()

    signal.signal(
        signal.SIGTERM,
        request_stop,
    )
    signal.signal(
        signal.SIGINT,
        request_stop,
    )

    exit_code = run_loop(
        settings,
        stop_event=stop_event,
    )

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
