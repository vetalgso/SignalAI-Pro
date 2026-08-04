from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

required_files = (
    "monitoring/README.md",
    "monitoring/prometheus/prometheus.yml",
    "monitoring/prometheus/rules/scheduler-alerts.yml",
    "monitoring/grafana/provisioning/datasources/prometheus.yml",
    "monitoring/grafana/provisioning/dashboards/signalai.yml",
    "monitoring/grafana/dashboards/signalai-scheduler-operations.json",
)

for filename in required_files:
    path = ROOT / filename
    assert path.is_file(), filename
    assert path.stat().st_size > 0, filename

compose = (
    ROOT / "docker-compose.yml"
).read_text(encoding="utf-8")

compose_values = (
    "prom/prometheus:v3.13.1",
    "grafana/grafana:13.1.1",
    "${PROMETHEUS_PORT:-9090}:9090",
    "${GRAFANA_PORT:-3001}:3000",
    "prometheus_data:/prometheus",
    "grafana_data:/var/lib/grafana",
    "  prometheus_data:",
    "  grafana_data:",
)

for value in compose_values:
    assert value in compose, value

compose_lines = compose.splitlines()

assert sum(
    line == "  prometheus:"
    for line in compose_lines
) == 1

assert sum(
    line == "  grafana:"
    for line in compose_lines
) == 1

prometheus = (
    ROOT / "monitoring/prometheus/prometheus.yml"
).read_text(encoding="utf-8")

for value in (
    "job_name: signalai-scheduler",
    "metrics_path: /api/v3/scheduler/metrics",
    "api:8000",
    "/etc/prometheus/rules/*.yml",
):
    assert value in prometheus, value

rules = (
    ROOT
    / "monitoring/prometheus/rules/scheduler-alerts.yml"
).read_text(encoding="utf-8")

expected_alerts = (
    "SignalAISchedulerMetricsTargetDown",
    "SignalAISchedulerNotReady",
    "SignalAISchedulerBackgroundLoopDown",
    "SignalAISchedulerBackgroundLoopStopping",
    "SignalAISchedulerBackgroundTickFailure",
    "SignalAISchedulerLatestCycleFailed",
    "SignalAISchedulerNewFailedCycle",
    "SignalAISchedulerConsecutiveFailures",
    "SignalAISchedulerDistributedLockDisabled",
    "SignalAISchedulerEnabledWithoutPayload",
)

for alert_name in expected_alerts:
    assert f"alert: {alert_name}" in rules, alert_name

assert rules.count("      - alert: ") == 10

datasource = (
    ROOT
    / "monitoring/grafana/provisioning/"
    "datasources/prometheus.yml"
).read_text(encoding="utf-8")

for value in (
    "uid: signalai-prometheus",
    "type: prometheus",
    "url: http://prometheus:9090",
    "isDefault: true",
):
    assert value in datasource, value

provider = (
    ROOT
    / "monitoring/grafana/provisioning/"
    "dashboards/signalai.yml"
).read_text(encoding="utf-8")

for value in (
    "folder: SignalAI",
    "type: file",
    "path: /var/lib/grafana/dashboards",
):
    assert value in provider, value

dashboard = json.loads(
    (
        ROOT
        / "monitoring/grafana/dashboards/"
        "signalai-scheduler-operations.json"
    ).read_text(encoding="utf-8")
)

assert dashboard["uid"] == "signalai-scheduler-ops"
assert dashboard["title"] == "SignalAI Scheduler Operations"
assert dashboard["refresh"] == "5s"
assert len(dashboard["panels"]) == 19

expressions = {
    target["expr"]
    for panel in dashboard["panels"]
    for target in panel.get("targets", [])
    if isinstance(target.get("expr"), str)
}

for metric in (
    "signalai_scheduler_ready",
    "signalai_scheduler_status",
    "signalai_scheduler_background_running",
    "signalai_scheduler_distributed_lock_enabled",
    "signalai_scheduler_cycles_total",
    "signalai_scheduler_last_cycle_failed",
    "ALERTS",
):
    assert any(
        metric in expression
        for expression in expressions
    ), metric

print("Monitoring files present: OK")
print("Docker Compose services and volumes: OK")
print("Prometheus scrape configuration: OK")
print("Prometheus alert rules: 10")
print("Grafana datasource provisioning: OK")
print("Grafana dashboard provisioning: OK")
print("Scheduler Operations dashboard panels: 19")

# v3.27 Alertmanager checks

alertmanager_files = (
    "monitoring/alertmanager/alertmanager.yml",
    "monitoring/alertmanager/templates/telegram.tmpl",
    "monitoring/alertmanager/secrets/.gitignore",
    "monitoring/alertmanager/secrets/README.md",
)

for filename in alertmanager_files:
    file_path = ROOT / filename
    assert file_path.is_file(), filename
    assert file_path.stat().st_size > 0, filename

compose_lines = compose.splitlines()

assert sum(
    line == "  alertmanager:"
    for line in compose_lines
) == 1

for value in (
    "prom/alertmanager:v0.32.1",
    "${ALERTMANAGER_PORT:-9093}:9093",
    "alertmanager_data:/alertmanager",
    "  alertmanager_data:",
    "./monitoring/alertmanager/alertmanager.yml:"
    "/etc/alertmanager/alertmanager.yml:ro",
    "./monitoring/alertmanager/templates:"
    "/etc/alertmanager/templates:ro",
    "./monitoring/alertmanager/secrets:"
    "/etc/alertmanager/secrets:ro",
):
    assert value in compose, value

for value in (
    "alerting:",
    "alertmanagers:",
    "alertmanager:9093",
):
    assert value in prometheus, value

alertmanager_config = (
    ROOT
    / "monitoring/alertmanager/alertmanager.yml"
).read_text(encoding="utf-8")

for value in (
    "receiver: signalai-telegram",
    "name: signalai-telegram",
    "telegram_configs:",
    "bot_token_file: "
    "/etc/alertmanager/secrets/telegram_bot_token",
    "chat_id_file: "
    "/etc/alertmanager/secrets/telegram_chat_id",
    "send_resolved: true",
    'message: \'{{ template "telegram.signalai.message" . }}\'',
):
    assert value in alertmanager_config, value

telegram_template = (
    ROOT
    / "monitoring/alertmanager/templates/telegram.tmpl"
).read_text(encoding="utf-8")

for value in (
    'define "telegram.signalai.message"',
    "SIGNALAI ALERT",
    "SIGNALAI RESOLVED",
    ".GroupLabels.alertname",
    ".CommonLabels.severity",
):
    assert value in telegram_template, value

secret_ignore = (
    ROOT
    / "monitoring/alertmanager/secrets/.gitignore"
).read_text(encoding="utf-8")

ignore_entries = {
    line.strip()
    for line in secret_ignore.splitlines()
    if line.strip() and not line.startswith("#")
}

assert "telegram_bot_token" in ignore_entries
assert "telegram_chat_id" in ignore_entries

readme = (
    ROOT / "monitoring/README.md"
).read_text(encoding="utf-8")

for value in (
    "## Alertmanager и Telegram",
    "http://localhost:9093",
    "send_resolved",
    "alertmanager_data",
):
    assert value in readme, value

print("Alertmanager Compose integration: OK")
print("Prometheus to Alertmanager routing: OK")
print("Telegram receiver configuration: OK")
print("Telegram firing/resolved template: OK")
print("Telegram secret protection rules: OK")
