from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from monitoring.e2e_exporter import (
    render_metrics,
)


class E2EExporterTests(unittest.TestCase):
    def test_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            metrics = render_metrics(
                report_file=root / "latest.json",
                history_file=root / "history.json",
                now_timestamp=100,
            )

        self.assertIn(
            "signalai_e2e_exporter_ready 1",
            metrics,
        )
        self.assertIn(
            "signalai_e2e_report_present 0",
            metrics,
        )
        self.assertIn(
            "signalai_e2e_report_valid 0",
            metrics,
        )
        self.assertIn(
            'signalai_e2e_last_run_status'
            '{status="SUCCESS"} 0',
            metrics,
        )
        self.assertIn(
            "signalai_e2e_history_entries 0",
            metrics,
        )

    def test_success_report_and_history(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            finished_at = datetime(
                2026,
                8,
                4,
                12,
                0,
                tzinfo=UTC,
            )

            report = {
                "schema_version": 1,
                "status": "SUCCESS",
                "run_id": "test-run",
                "finished_at": (
                    finished_at.isoformat()
                ),
                "duration_seconds": 12.5,
                "timeout_seconds": 90,
                "runtime_rule_removed": True,
                "telegram": {
                    "notifications_total": 4,
                    "failures_total": 0,
                },
            }

            history = [
                {"status": "FAILURE"},
                {"status": "SUCCESS"},
                {"status": "SUCCESS"},
            ]

            (root / "latest.json").write_text(
                json.dumps(report),
                encoding="utf-8",
            )

            (root / "history.json").write_text(
                json.dumps(history),
                encoding="utf-8",
            )

            metrics = render_metrics(
                report_file=root / "latest.json",
                history_file=root / "history.json",
                now_timestamp=(
                    finished_at.timestamp()
                    + 30
                ),
            )

        self.assertIn(
            "signalai_e2e_report_valid 1",
            metrics,
        )
        self.assertIn(
            'signalai_e2e_last_run_status'
            '{status="SUCCESS"} 1',
            metrics,
        )
        self.assertIn(
            'signalai_e2e_last_run_status'
            '{status="FAILURE"} 0',
            metrics,
        )
        self.assertIn(
            "signalai_e2e_last_run_age_seconds 30",
            metrics,
        )
        self.assertIn(
            "signalai_e2e_last_run_duration_seconds "
            "12.5",
            metrics,
        )
        self.assertIn(
            "signalai_e2e_last_run_"
            "runtime_rule_removed 1",
            metrics,
        )
        self.assertIn(
            "signalai_e2e_last_run_"
            "telegram_notifications 4",
            metrics,
        )
        self.assertIn(
            "signalai_e2e_last_run_"
            "telegram_failures 0",
            metrics,
        )
        self.assertIn(
            "signalai_e2e_history_entries 3",
            metrics,
        )
        self.assertIn(
            'signalai_e2e_history_runs'
            '{status="SUCCESS"} 2',
            metrics,
        )
        self.assertIn(
            'signalai_e2e_history_runs'
            '{status="FAILURE"} 1',
            metrics,
        )

    def test_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            (root / "latest.json").write_text(
                "{invalid",
                encoding="utf-8",
            )

            (root / "history.json").write_text(
                "{}",
                encoding="utf-8",
            )

            metrics = render_metrics(
                report_file=root / "latest.json",
                history_file=root / "history.json",
                now_timestamp=100,
            )

        self.assertIn(
            "signalai_e2e_report_present 1",
            metrics,
        )
        self.assertIn(
            "signalai_e2e_report_valid 0",
            metrics,
        )
        self.assertIn(
            "signalai_e2e_history_present 1",
            metrics,
        )
        self.assertIn(
            "signalai_e2e_history_valid 0",
            metrics,
        )


if __name__ == "__main__":
    unittest.main()
