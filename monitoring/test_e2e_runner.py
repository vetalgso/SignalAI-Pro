from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from datetime import (
    UTC,
    datetime,
    timedelta,
)
from pathlib import Path

from monitoring.e2e_runner import (
    INTERRUPTED_RUN_EXIT_CODE,
    LOCK_CONFLICT_EXIT_CODE,
    PROCESS_TIMEOUT_EXIT_CODE,
    RunnerSettings,
    build_self_test_command,
    initial_state,
    prepare_startup_state,
    run_once,
)


class E2ERunnerTests(unittest.TestCase):
    def make_settings(
        self,
        root: Path,
    ) -> RunnerSettings:
        self_test = root / "e2e_self_test.py"
        self_test.write_text(
            "# test\n",
            encoding="utf-8",
        )

        return RunnerSettings(
            self_test=self_test,
            report_file=root / "latest.json",
            history_file=root / "history.json",
            state_file=(
                root / "runner-state.json"
            ),
            startup_delay_seconds=5,
            interval_seconds=86400,
            retry_delay_seconds=900,
            self_test_timeout_seconds=90,
            process_timeout_seconds=600,
            history_limit=20,
        )

    def test_build_self_test_command(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = self.make_settings(
                root
            )

            command = (
                build_self_test_command(
                    settings
                )
            )

        self.assertEqual(
            command[1],
            str(settings.self_test),
        )
        self.assertIn(
            "--timeout",
            command,
        )
        self.assertIn(
            "--report-file",
            command,
        )
        self.assertIn(
            "--history-file",
            command,
        )
        self.assertIn(
            "--history-limit",
            command,
        )

    def test_success_uses_interval(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = self.make_settings(
                root
            )

            started = datetime(
                2026,
                8,
                4,
                12,
                0,
                tzinfo=UTC,
            )
            finished = datetime(
                2026,
                8,
                4,
                12,
                1,
                tzinfo=UTC,
            )

            times = iter(
                [started, finished]
            )

            state = initial_state(
                settings,
                now=started,
            )

            def success(
                command: list[str],
                **kwargs: object,
            ) -> subprocess.CompletedProcess[
                str
            ]:
                del kwargs

                return subprocess.CompletedProcess(
                    command,
                    0,
                )

            exit_code, delay = run_once(
                settings,
                state,
                schedule_next=True,
                command_runner=success,
                now_provider=lambda: next(
                    times
                ),
            )

            persisted = json.loads(
                settings.state_file.read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(delay, 86400)
        self.assertEqual(
            persisted["last_result"],
            "SUCCESS",
        )
        self.assertEqual(
            persisted["runner_status"],
            "WAITING",
        )
        self.assertEqual(
            persisted["runs_total"],
            1,
        )
        self.assertEqual(
            persisted["successes_total"],
            1,
        )
        self.assertEqual(
            persisted[
                "consecutive_failures"
            ],
            0,
        )
        self.assertEqual(
            persisted["next_run_at"],
            (
                finished
                .replace()
                + __import__(
                    "datetime"
                ).timedelta(
                    seconds=86400
                )
            ).isoformat(),
        )

    def test_failure_uses_retry_delay(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = self.make_settings(
                root
            )

            moment = datetime(
                2026,
                8,
                4,
                12,
                0,
                tzinfo=UTC,
            )

            state = initial_state(
                settings,
                now=moment,
            )

            def failure(
                command: list[str],
                **kwargs: object,
            ) -> subprocess.CompletedProcess[
                str
            ]:
                del kwargs

                return subprocess.CompletedProcess(
                    command,
                    5,
                )

            exit_code, delay = run_once(
                settings,
                state,
                schedule_next=True,
                command_runner=failure,
                now_provider=lambda: moment,
            )

            persisted = json.loads(
                settings.state_file.read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(exit_code, 5)
        self.assertEqual(delay, 900)
        self.assertEqual(
            persisted["last_result"],
            "FAILURE",
        )
        self.assertEqual(
            persisted["failures_total"],
            1,
        )
        self.assertEqual(
            persisted[
                "consecutive_failures"
            ],
            1,
        )
        self.assertEqual(
            persisted["successes_total"],
            0,
        )

    def test_lock_conflict_is_not_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = self.make_settings(
                root
            )

            moment = datetime(
                2026,
                8,
                4,
                12,
                0,
                tzinfo=UTC,
            )

            state = initial_state(
                settings,
                now=moment,
            )

            def locked(
                command: list[str],
                **kwargs: object,
            ) -> subprocess.CompletedProcess[
                str
            ]:
                del kwargs

                return subprocess.CompletedProcess(
                    command,
                    LOCK_CONFLICT_EXIT_CODE,
                )

            exit_code, delay = run_once(
                settings,
                state,
                schedule_next=True,
                command_runner=locked,
                now_provider=lambda: moment,
            )

            persisted = json.loads(
                settings.state_file.read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(
            exit_code,
            LOCK_CONFLICT_EXIT_CODE,
        )
        self.assertEqual(delay, 900)
        self.assertEqual(
            persisted["last_result"],
            "LOCKED",
        )
        self.assertEqual(
            persisted[
                "lock_conflicts_total"
            ],
            1,
        )
        self.assertEqual(
            persisted["failures_total"],
            0,
        )
        self.assertEqual(
            persisted[
                "consecutive_failures"
            ],
            0,
        )

    def test_process_timeout_is_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = self.make_settings(
                root
            )

            moment = datetime(
                2026,
                8,
                4,
                12,
                0,
                tzinfo=UTC,
            )

            state = initial_state(
                settings,
                now=moment,
            )

            def timeout(
                command: list[str],
                **kwargs: object,
            ) -> subprocess.CompletedProcess[
                str
            ]:
                del kwargs

                raise subprocess.TimeoutExpired(
                    command,
                    600,
                )

            exit_code, delay = run_once(
                settings,
                state,
                schedule_next=False,
                command_runner=timeout,
                now_provider=lambda: moment,
            )

            persisted = json.loads(
                settings.state_file.read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(
            exit_code,
            PROCESS_TIMEOUT_EXIT_CODE,
        )
        self.assertEqual(delay, 900)
        self.assertEqual(
            persisted["last_result"],
            "FAILURE",
        )
        self.assertEqual(
            persisted["runner_status"],
            "COMPLETED",
        )
        self.assertEqual(
            persisted["last_error"]["type"],
            "TimeoutExpired",
        )
        self.assertIsNone(
            persisted["next_run_at"]
        )


    def test_future_waiting_state_resumes_schedule(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = self.make_settings(
                root
            )

            previous_start = datetime(
                2026,
                8,
                4,
                10,
                0,
                tzinfo=UTC,
            )

            now = datetime(
                2026,
                8,
                4,
                12,
                0,
                tzinfo=UTC,
            )

            next_run = (
                now
                + timedelta(
                    minutes=10
                )
            )

            previous = initial_state(
                settings,
                now=previous_start,
            )

            previous.update(
                {
                    "runner_status": (
                        "WAITING"
                    ),
                    "last_result": (
                        "SUCCESS"
                    ),
                    "updated_at": (
                        previous_start
                        .isoformat()
                    ),
                    "next_run_at": (
                        next_run.isoformat()
                    ),
                    "runs_total": 7,
                    "successes_total": 6,
                    "failures_total": 1,
                }
            )

            settings.state_file.write_text(
                json.dumps(previous),
                encoding="utf-8",
            )

            state, delay = (
                prepare_startup_state(
                    settings,
                    now=now,
                )
            )

        self.assertEqual(delay, 600)
        self.assertEqual(
            state["runner_status"],
            "WAITING",
        )
        self.assertEqual(
            state["next_run_at"],
            next_run.isoformat(),
        )
        self.assertEqual(
            state["runs_total"],
            7,
        )
        self.assertEqual(
            state["successes_total"],
            6,
        )
        self.assertEqual(
            state["restart_count"],
            1,
        )
        self.assertTrue(
            state["recovered"]
        )
        self.assertEqual(
            state[
                "recovered_from_status"
            ],
            "WAITING",
        )
        self.assertEqual(
            state["recovery_reason"],
            "RESUMED_SCHEDULE",
        )

    def test_overdue_waiting_state_runs_immediately(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = self.make_settings(
                root
            )

            now = datetime(
                2026,
                8,
                4,
                12,
                0,
                tzinfo=UTC,
            )

            previous = initial_state(
                settings,
                now=(
                    now
                    - timedelta(
                        hours=2
                    )
                ),
            )

            previous.update(
                {
                    "runner_status": (
                        "WAITING"
                    ),
                    "next_run_at": (
                        now
                        - timedelta(
                            minutes=20
                        )
                    ).isoformat(),
                    "runs_total": 3,
                    "successes_total": 3,
                }
            )

            settings.state_file.write_text(
                json.dumps(previous),
                encoding="utf-8",
            )

            state, delay = (
                prepare_startup_state(
                    settings,
                    now=now,
                )
            )

        self.assertEqual(delay, 0)
        self.assertEqual(
            state["next_run_at"],
            now.isoformat(),
        )
        self.assertEqual(
            state["recovery_reason"],
            "OVERDUE_SCHEDULE",
        )
        self.assertEqual(
            state["runs_total"],
            3,
        )

    def test_interrupted_run_becomes_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = self.make_settings(
                root
            )

            now = datetime(
                2026,
                8,
                4,
                12,
                0,
                tzinfo=UTC,
            )

            previous = initial_state(
                settings,
                now=(
                    now
                    - timedelta(
                        hours=1
                    )
                ),
            )

            previous.update(
                {
                    "runner_status": (
                        "RUNNING"
                    ),
                    "next_run_at": None,
                    "runs_total": 4,
                    "successes_total": 2,
                    "failures_total": 2,
                    "consecutive_failures": 2,
                    "last_run_started_at": (
                        now
                        - timedelta(
                            minutes=5
                        )
                    ).isoformat(),
                }
            )

            settings.state_file.write_text(
                json.dumps(previous),
                encoding="utf-8",
            )

            state, delay = (
                prepare_startup_state(
                    settings,
                    now=now,
                )
            )

        self.assertEqual(delay, 900)
        self.assertEqual(
            state["runner_status"],
            "WAITING",
        )
        self.assertEqual(
            state["last_result"],
            "FAILURE",
        )
        self.assertEqual(
            state["last_exit_code"],
            INTERRUPTED_RUN_EXIT_CODE,
        )
        self.assertEqual(
            state["runs_total"],
            5,
        )
        self.assertEqual(
            state["failures_total"],
            3,
        )
        self.assertEqual(
            state[
                "consecutive_failures"
            ],
            3,
        )
        self.assertEqual(
            state["last_error"]["type"],
            "InterruptedRun",
        )
        self.assertEqual(
            state["recovery_reason"],
            "INTERRUPTED_RUN",
        )
        self.assertEqual(
            state["next_run_at"],
            (
                now
                + timedelta(
                    seconds=900
                )
            ).isoformat(),
        )

    def test_invalid_state_is_reset(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = self.make_settings(
                root
            )

            settings.state_file.write_text(
                "{invalid",
                encoding="utf-8",
            )

            now = datetime(
                2026,
                8,
                4,
                12,
                0,
                tzinfo=UTC,
            )

            state, delay = (
                prepare_startup_state(
                    settings,
                    now=now,
                )
            )

            persisted = json.loads(
                settings.state_file.read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(delay, 5)
        self.assertEqual(
            state["runner_status"],
            "WAITING",
        )
        self.assertEqual(
            state["runs_total"],
            0,
        )
        self.assertEqual(
            state["restart_count"],
            0,
        )
        self.assertFalse(
            state["recovered"]
        )
        self.assertEqual(
            state["recovery_reason"],
            "INVALID_STATE_RESET",
        )
        self.assertEqual(
            persisted[
                "recovery_reason"
            ],
            "INVALID_STATE_RESET",
        )


if __name__ == "__main__":
    unittest.main()
