#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import string
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_RULE = (
    ROOT
    / "monitoring/prometheus/rules/"
    "e2e-self-test.runtime.yml"
)

PROMETHEUS_URL = "http://localhost:9090"
ALERTMANAGER_URL = "http://localhost:9093"

ALERT_NAME = "SignalAIMonitoringE2ESelfTest"


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


def execute(timeout: float) -> None:
    run_id = make_run_id()
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

    args = parser.parse_args()

    if args.timeout <= 0:
        parser.error(
            "--timeout must be positive"
        )

    execute(args.timeout)


if __name__ == "__main__":
    main()
