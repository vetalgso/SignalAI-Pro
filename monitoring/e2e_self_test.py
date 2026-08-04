#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import os
import random
import socket
import string
import sys
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterator


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_RULE = (
    ROOT
    / "monitoring/prometheus/rules/"
    "e2e-self-test.runtime.yml"
)

LOCK_FILE = Path(
    os.environ.get(
        "SIGNALAI_E2E_LOCK_FILE",
        "/tmp/signalai-monitoring-e2e.lock",
    )
)

REPORT_DIR = Path(
    os.environ.get(
        "SIGNALAI_E2E_REPORT_DIR",
        str(ROOT / "monitoring/e2e-reports"),
    )
)

DEFAULT_REPORT_FILE = Path(
    os.environ.get(
        "SIGNALAI_E2E_REPORT_FILE",
        str(REPORT_DIR / "latest.json"),
    )
)

DEFAULT_HISTORY_FILE = Path(
    os.environ.get(
        "SIGNALAI_E2E_HISTORY_FILE",
        str(REPORT_DIR / "history.json"),
    )
)

DEFAULT_HISTORY_LIMIT = 20

PROMETHEUS_URL = "http://localhost:9090"
ALERTMANAGER_URL = "http://localhost:9093"

ALERT_NAME = "SignalAIMonitoringE2ESelfTest"


class SelfTestAlreadyRunning(RuntimeError):
    pass


@contextmanager
def exclusive_run_lock() -> Iterator[None]:
    LOCK_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with LOCK_FILE.open(
        "a+",
        encoding="utf-8",
    ) as lock_file:
        try:
            fcntl.flock(
                lock_file.fileno(),
                fcntl.LOCK_EX
                | fcntl.LOCK_NB,
            )
        except BlockingIOError as error:
            lock_file.seek(0)
            owner = lock_file.read().strip()

            owner_details = (
                f" Owner: {owner}"
                if owner
                else ""
            )

            raise SelfTestAlreadyRunning(
                "Another monitoring E2E "
                "self-test is active."
                f"{owner_details}"
            ) from error

        owner = {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "started_at": datetime.now(
                UTC
            ).isoformat(),
        }

        lock_file.seek(0)
        lock_file.truncate()
        json.dump(
            owner,
            lock_file,
            sort_keys=True,
        )
        lock_file.write("\n")
        lock_file.flush()
        os.fsync(lock_file.fileno())

        try:
            yield
        finally:
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.flush()
            os.fsync(lock_file.fileno())

            fcntl.flock(
                lock_file.fileno(),
                fcntl.LOCK_UN,
            )


def utc_now() -> datetime:
    return datetime.now(UTC)


def atomic_write_json(
    path: Path,
    payload: Any,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_name(
        f".{path.name}.{os.getpid()}.tmp"
    )

    temporary_path.write_text(
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
        temporary_path,
        path,
    )


def persist_report(
    report: dict[str, Any],
    *,
    report_file: Path,
    history_file: Path,
    history_limit: int,
) -> None:
    if history_limit <= 0:
        raise ValueError(
            "history_limit must be positive"
        )

    atomic_write_json(
        report_file,
        report,
    )

    if history_file.exists():
        history = json.loads(
            history_file.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(history, list):
            raise ValueError(
                "E2E history must contain "
                "a JSON array."
            )
    else:
        history = []

    history.append(report)
    history = history[-history_limit:]

    atomic_write_json(
        history_file,
        history,
    )


def optional_metric(
    metric: Callable[[], float],
) -> int | None:
    try:
        return int(metric())
    except Exception:
        return None


def build_report(
    *,
    run_id: str,
    status: str,
    timeout: float,
    started_at: datetime,
    started_monotonic: float,
    error: BaseException | None,
) -> dict[str, Any]:
    finished_at = utc_now()

    return {
        "schema_version": 1,
        "status": status,
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round(
            time.monotonic()
            - started_monotonic,
            3,
        ),
        "timeout_seconds": timeout,
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "runtime_rule_removed": (
            not RUNTIME_RULE.exists()
        ),
        "telegram": {
            "notifications_total": (
                optional_metric(
                    telegram_notifications
                )
            ),
            "failures_total": (
                optional_metric(
                    telegram_failures
                )
            ),
        },
        "error": (
            None
            if error is None
            else {
                "type": type(error).__name__,
                "message": str(error),
            }
        ),
    }


def http_json(
    url: str,
    *,
    method: str = "GET",
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        method=method,
    )

    with urllib.request.urlopen(
        request,
        timeout=10,
    ) as response:
        return json.load(response)


def http_ready(url: str) -> None:
    request = urllib.request.Request(url)

    with urllib.request.urlopen(
        request,
        timeout=10,
    ) as response:
        if response.status != 200:
            raise RuntimeError(
                f"Readiness failed: {url}"
            )


def reload_prometheus() -> None:
    request = urllib.request.Request(
        f"{PROMETHEUS_URL}/-/reload",
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=10,
    ) as response:
        if response.status not in (200, 204):
            raise RuntimeError(
                "Prometheus reload failed: "
                f"HTTP {response.status}"
            )


def prometheus_query(
    expression: str,
) -> float:
    url = (
        f"{PROMETHEUS_URL}/api/v1/query?"
        + urllib.parse.urlencode(
            {"query": expression}
        )
    )

    data = http_json(url)
    result = data["data"]["result"]

    return sum(
        float(series["value"][1])
        for series in result
    )


def telegram_notifications() -> float:
    return prometheus_query(
        "sum("
        "alertmanager_notifications_total{"
        'job="signalai-alertmanager",'
        'integration="telegram"'
        "}"
        ")"
    )


def telegram_failures() -> float:
    return prometheus_query(
        "sum("
        "alertmanager_notifications_failed_total{"
        'job="signalai-alertmanager",'
        'integration="telegram"'
        "}"
        ")"
    )


def prometheus_alert_state(
    run_id: str,
) -> str | None:
    data = http_json(
        f"{PROMETHEUS_URL}/api/v1/alerts"
    )

    for alert in data["data"]["alerts"]:
        labels = alert.get("labels", {})

        if (
            labels.get("alertname") == ALERT_NAME
            and labels.get("run_id") == run_id
        ):
            return alert.get("state")

    return None


def alertmanager_alert_state(
    run_id: str,
) -> str | None:
    alerts = http_json(
        f"{ALERTMANAGER_URL}/api/v2/alerts"
    )

    for alert in alerts:
        labels = alert.get("labels", {})

        if (
            labels.get("alertname") == ALERT_NAME
            and labels.get("run_id") == run_id
        ):
            return (
                alert.get("status", {})
                .get("state")
            )

    return None


def rule_is_loaded(run_id: str) -> bool:
    data = http_json(
        f"{PROMETHEUS_URL}/api/v1/rules"
    )

    for group in data["data"]["groups"]:
        for rule in group["rules"]:
            if rule.get("name") != ALERT_NAME:
                continue

            labels = rule.get("labels", {})

            if labels.get("run_id") == run_id:
                return True

    return False


def write_rule(
    *,
    run_id: str,
    instance: str,
    firing: bool,
) -> None:
    expression = (
        "vector(1) > 0"
        if firing
        else "vector(0) > 0"
    )

    state = (
        "FIRING"
        if firing
        else "RESOLVED"
    )

    rule = f"""groups:
  - name: signalai-monitoring-e2e-{run_id}
    interval: 1s
    rules:
      - alert: {ALERT_NAME}
        expr: {expression}
        labels:
          severity: critical
          component: monitoring-e2e
          self_test: "true"
          instance: "{instance}"
          job: signalai-monitoring-self-test
          run_id: "{run_id}"
        annotations:
          summary: SignalAI monitoring E2E self-test
          description: "{state} phase for E2E run {run_id}."
"""

    RUNTIME_RULE.write_text(
        rule,
        encoding="utf-8",
    )


def remove_runtime_rule() -> None:
    RUNTIME_RULE.unlink(
        missing_ok=True,
    )

    reload_prometheus()


def wait_for(
    description: str,
    predicate: Callable[[], bool],
    *,
    timeout: float,
) -> None:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if predicate():
            print(f"{description}: OK")
            return

        time.sleep(1)

    raise TimeoutError(
        f"Timeout while waiting for: {description}"
    )


def make_run_id() -> str:
    timestamp = datetime.now(UTC).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    suffix = "".join(
        random.choices(
            string.ascii_lowercase
            + string.digits,
            k=6,
        )
    )

    return f"{timestamp}-{suffix}"


def _execute_unlocked(
    timeout: float,
    run_id: str,
) -> None:
    instance = f"e2e-{run_id}"

    print(f"Run ID: {run_id}")

    http_ready(
        f"{PROMETHEUS_URL}/-/ready"
    )
    http_ready(
        f"{ALERTMANAGER_URL}/-/ready"
    )

    print("Prometheus ready: OK")
    print("Alertmanager ready: OK")

    if RUNTIME_RULE.exists():
        raise RuntimeError(
            f"Stale runtime rule exists: "
            f"{RUNTIME_RULE}"
        )

    notifications_before = (
        telegram_notifications()
    )
    failures_before = telegram_failures()

    print(
        "Telegram notifications before:",
        int(notifications_before),
    )
    print(
        "Telegram failures before:",
        int(failures_before),
    )

    firing_sent = False

    try:
        print()
        print("=== FIRING phase ===")

        write_rule(
            run_id=run_id,
            instance=instance,
            firing=True,
        )
        reload_prometheus()

        wait_for(
            "Runtime rule loaded",
            lambda: rule_is_loaded(run_id),
            timeout=timeout,
        )

        wait_for(
            "Prometheus alert firing",
            lambda: (
                prometheus_alert_state(run_id)
                == "firing"
            ),
            timeout=timeout,
        )

        wait_for(
            "Alertmanager alert active",
            lambda: (
                alertmanager_alert_state(run_id)
                == "active"
            ),
            timeout=timeout,
        )

        wait_for(
            "Telegram firing notification",
            lambda: (
                telegram_notifications()
                >= notifications_before + 1
            ),
            timeout=timeout,
        )

        firing_sent = True

        if telegram_failures() != failures_before:
            raise RuntimeError(
                "Telegram failure counter increased "
                "during firing phase."
            )

        print("Telegram firing failures: 0")

        print()
        print("=== RESOLVED phase ===")

        write_rule(
            run_id=run_id,
            instance=instance,
            firing=False,
        )
        reload_prometheus()

        wait_for(
            "Prometheus alert resolved",
            lambda: (
                prometheus_alert_state(run_id)
                is None
            ),
            timeout=timeout,
        )

        wait_for(
            "Telegram resolved notification",
            lambda: (
                telegram_notifications()
                >= notifications_before + 2
            ),
            timeout=timeout,
        )

        if telegram_failures() != failures_before:
            raise RuntimeError(
                "Telegram failure counter increased "
                "during resolved phase."
            )

        notifications_after = (
            telegram_notifications()
        )

        print("Telegram resolved failures: 0")
        print()
        print(
            "Telegram notification delta:",
            int(
                notifications_after
                - notifications_before
            ),
        )
        print("E2E result: SUCCESS")

    finally:
        if (
            firing_sent
            and RUNTIME_RULE.exists()
        ):
            write_rule(
                run_id=run_id,
                instance=instance,
                firing=False,
            )

            try:
                reload_prometheus()
                time.sleep(2)
            except Exception:
                pass

        if RUNTIME_RULE.exists():
            try:
                remove_runtime_rule()
            except Exception as error:
                print(
                    "Cleanup warning:",
                    error,
                )

        print(
            "Runtime rule removed:",
            not RUNTIME_RULE.exists(),
        )



def run_with_report(
    *,
    timeout: float,
    report_file: Path,
    history_file: Path,
    history_limit: int,
) -> dict[str, Any]:
    with exclusive_run_lock():
        run_id = make_run_id()
        started_at = utc_now()
        started_monotonic = time.monotonic()

        try:
            _execute_unlocked(
                timeout,
                run_id,
            )
        except BaseException as error:
            report = build_report(
                run_id=run_id,
                status="FAILURE",
                timeout=timeout,
                started_at=started_at,
                started_monotonic=(
                    started_monotonic
                ),
                error=error,
            )

            try:
                persist_report(
                    report,
                    report_file=report_file,
                    history_file=history_file,
                    history_limit=history_limit,
                )
            except Exception as report_error:
                error.add_note(
                    "JSON report persistence "
                    "failed: "
                    f"{report_error}"
                )

            raise

        report = build_report(
            run_id=run_id,
            status="SUCCESS",
            timeout=timeout,
            started_at=started_at,
            started_monotonic=(
                started_monotonic
            ),
            error=None,
        )

        persist_report(
            report,
            report_file=report_file,
            history_file=history_file,
            history_limit=history_limit,
        )

        print(
            "JSON report:",
            report_file,
        )
        print(
            "JSON history:",
            history_file,
        )

        return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run SignalAI Prometheus -> "
            "Alertmanager -> Telegram E2E test."
        )
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=60,
        help=(
            "Timeout for each E2E phase "
            "in seconds."
        ),
    )

    parser.add_argument(
        "--report-file",
        type=Path,
        default=DEFAULT_REPORT_FILE,
        help=(
            "Path for the latest JSON report."
        ),
    )

    parser.add_argument(
        "--history-file",
        type=Path,
        default=DEFAULT_HISTORY_FILE,
        help=(
            "Path for JSON execution history."
        ),
    )

    parser.add_argument(
        "--history-limit",
        type=int,
        default=DEFAULT_HISTORY_LIMIT,
        help=(
            "Maximum number of reports "
            "stored in history."
        ),
    )

    args = parser.parse_args()

    if args.timeout <= 0:
        parser.error(
            "--timeout must be positive"
        )

    if args.history_limit <= 0:
        parser.error(
            "--history-limit must be positive"
        )

    if (
        args.report_file.resolve()
        == args.history_file.resolve()
    ):
        parser.error(
            "--report-file and --history-file "
            "must be different"
        )

    try:
        run_with_report(
            timeout=args.timeout,
            report_file=args.report_file,
            history_file=args.history_file,
            history_limit=args.history_limit,
        )
    except SelfTestAlreadyRunning as error:
        print(
            "E2E self-test already running:",
            error,
            file=sys.stderr,
        )
        raise SystemExit(75) from error


if __name__ == "__main__":
    main()
