from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

required_files = (
    "monitoring/README.md",
    "monitoring/prometheus/prometheus.yml",
    "monitoring/prometheus/rules/scheduler-alerts.yml",
    "monitoring/prometheus/rules/alertmanager-alerts.yml",
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
assert len(dashboard["panels"]) == 39

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
print("Scheduler Prometheus alert rules: 10")
print("Grafana datasource provisioning: OK")
print("Grafana dashboard provisioning: OK")
print("Scheduler Operations dashboard panels: 39")

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

# v3.28 routing and silence checks

silence_helper_path = (
    ROOT
    / "monitoring/alertmanager/silence.sh"
)

assert silence_helper_path.is_file()
assert silence_helper_path.stat().st_size > 0
assert silence_helper_path.stat().st_mode & 0o111

assert (
    alertmanager_config.count(
        "telegram_configs:"
    )
    == 3
)

assert (
    alertmanager_config.count(
        "source_matchers:"
    )
    == 3
)

assert (
    alertmanager_config.count(
        "target_matchers:"
    )
    == 3
)

assert (
    alertmanager_config.count(
        "  - name: signalai-telegram-"
    )
    == 3
)

assert (
    alertmanager_config.count(
        "    - receiver: signalai-telegram-"
    )
    == 4
)

for value in (
    "receiver: signalai-telegram-critical",
    "receiver: signalai-telegram-warning",
    "receiver: signalai-telegram-info",
    'severity="critical"',
    'severity="warning"',
    'severity="info"',
    "group_wait: 5s",
    "group_wait: 30s",
    "group_wait: 2m",
    "repeat_interval: 1h",
    "repeat_interval: 4h",
    "repeat_interval: 12h",
    "inhibit_rules:",
    'alertname="SignalAISchedulerMetricsTargetDown"',
    'alertname="SignalAISchedulerNotReady"',
    'alertname="SignalAISchedulerConsecutiveFailures"',
    'alertname=~"SignalAISchedulerLatestCycleFailed|'
    'SignalAISchedulerNewFailedCycle"',
):
    assert value in alertmanager_config, value

silence_helper = silence_helper_path.read_text(
    encoding="utf-8"
)

for value in (
    "silence.sh add <duration>",
    "silence.sh list",
    "silence.sh ids",
    "silence.sh expire",
    "amtool_cmd silence add",
    "amtool_cmd silence query",
    "amtool_cmd silence expire",
    "SILENCE_AUTHOR",
    "ALERTMANAGER_URL",
):
    assert value in silence_helper, value

for value in (
    "## Severity routing",
    "## Inhibition rules",
    "## Управление silences",
    "signalai-telegram-critical",
    "signalai-telegram-warning",
    "signalai-telegram-info",
    "monitoring/alertmanager/silence.sh",
):
    assert value in readme, value

print("Severity routing configuration: OK")
print("Critical/warning/info receivers: 3")
print("Alert inhibition rules: 3")
print("Silence management helper: OK")
print("Silence helper executable mode: OK")
print("Routing and silence documentation: OK")

# v3.29 Alertmanager observability checks

alertmanager_rules_path = (
    ROOT
    / "monitoring/prometheus/rules/"
    "alertmanager-alerts.yml"
)

alertmanager_rules = alertmanager_rules_path.read_text(
    encoding="utf-8"
)

expected_alertmanager_alerts = (
    "SignalAIAlertmanagerMetricsTargetDown",
    "SignalAIAlertmanagerConfigReloadFailed",
    "SignalAIAlertmanagerTelegramNotificationFailure",
    "SignalAIAlertmanagerUnprocessedAlerts",
    "SignalAIAlertmanagerInvalidAlertsReceived",
    "SignalAIAlertmanagerAggregationGroupLimitReached",
    "SignalAIAlertmanagerActiveSilences",
    "SignalAIAlertmanagerSuppressedAlerts",
    "SignalAIAlertmanagerUnexpectedClusterMembers",
)

for alert_name in expected_alertmanager_alerts:
    assert (
        f"alert: {alert_name}"
        in alertmanager_rules
    ), alert_name

assert (
    alertmanager_rules.count("      - alert: ")
    == 9
)

for value in (
    "job_name: signalai-alertmanager",
    "metrics_path: /metrics",
    "alertmanager:9093",
    "service: signalai-alertmanager",
    "component: alerting",
):
    assert value in prometheus, value

alertmanager_dashboard_titles = {
    "Alertmanager Operations",
    "Alertmanager Target",
    "Alertmanager Config Reload",
    "Alertmanager Cluster Members",
    "Active Alertmanager Silences",
    "Active Alertmanager Alerts",
    "Suppressed Alertmanager Alerts",
    "Telegram Failures (24h)",
    "Telegram Notification Pipeline",
    "Alertmanager State History",
    "Firing Alertmanager Alerts",
}

dashboard_titles = {
    panel.get("title")
    for panel in dashboard["panels"]
}

assert (
    alertmanager_dashboard_titles
    <= dashboard_titles
)

for metric in (
    "alertmanager_config_last_reload_successful",
    "alertmanager_cluster_members",
    "alertmanager_alerts",
    "alertmanager_silences",
    "alertmanager_notifications_total",
    "alertmanager_notifications_failed_total",
):
    assert any(
        metric in expression
        for expression in expressions
    ), metric

assert len(dashboard["panels"]) == 39

panel_ids = [
    panel["id"]
    for panel in dashboard["panels"]
]

assert len(panel_ids) == len(set(panel_ids))

for value in (
    "## Мониторинг Alertmanager",
    "signalai-alertmanager",
    "alertmanager-alerts.yml",
    "Alertmanager Operations",
    "signalai-scheduler-ops",
):
    assert value in readme, value

print("Alertmanager metrics scrape job: OK")
print("Alertmanager Prometheus alert rules: 9")
print("Alertmanager dashboard panels: 11")
print("Total dashboard panels: 39")
print("Dashboard panel IDs unique: OK")
print("Alertmanager monitoring documentation: OK")

# v3.30 monitoring E2E route checks

runtime_rule_ignore_path = (
    ROOT
    / "monitoring/prometheus/rules/.gitignore"
)

assert runtime_rule_ignore_path.is_file()

runtime_rule_ignore = (
    runtime_rule_ignore_path.read_text(
        encoding="utf-8"
    )
)

assert (
    "e2e-self-test.runtime.yml"
    in runtime_rule_ignore.splitlines()
)

for value in (
    'self_test="true"',
    "group_wait: 1s",
    "group_interval: 5s",
):
    assert value in alertmanager_config, value

assert (
    alertmanager_config.count(
        "    - receiver: signalai-telegram-"
    )
    == 4
)

print("Monitoring E2E self-test route: OK")
print("Monitoring E2E runtime rule ignore: OK")

# v3.30 monitoring E2E script checks

e2e_script_path = (
    ROOT
    / "monitoring/e2e_self_test.py"
)

assert e2e_script_path.is_file()
assert e2e_script_path.stat().st_size > 0
assert e2e_script_path.stat().st_mode & 0o111

e2e_script = e2e_script_path.read_text(
    encoding="utf-8"
)

assert e2e_script.startswith(
    "#!/usr/bin/env python3\n"
)

for value in (
    "SignalAIMonitoringE2ESelfTest",
    "e2e-self-test.runtime.yml",
    "self_test: \"true\"",
    "Telegram firing notification",
    "Telegram resolved notification",
    "Telegram notification delta",
    "E2E result: SUCCESS",
    "Runtime rule removed:",
    "alertmanager_notifications_total",
    "alertmanager_notifications_failed_total",
):
    assert value in e2e_script, value

runtime_rule_path = (
    ROOT
    / "monitoring/prometheus/rules/"
    "e2e-self-test.runtime.yml"
)

assert not runtime_rule_path.exists()

for value in (
    "## Monitoring E2E self-test",
    "Prometheus -> Alertmanager -> Telegram",
    "./monitoring/e2e_self_test.py --timeout 90",
    'self_test="true"',
    "SIGNALAI ALERT",
    "SIGNALAI RESOLVED",
    "e2e-self-test.runtime.yml",
):
    assert value in readme, value

print("Monitoring E2E self-test script: OK")
print("Monitoring E2E script executable mode: OK")
print("Monitoring E2E runtime cleanup: OK")
print("Monitoring E2E documentation: OK")

# v3.31 E2E parallel-run protection

for value in (
    "import fcntl",
    "SIGNALAI_E2E_LOCK_FILE",
    "signalai-monitoring-e2e.lock",
    "class SelfTestAlreadyRunning",
    "def exclusive_run_lock()",
    "fcntl.LOCK_EX",
    "fcntl.LOCK_NB",
    "with exclusive_run_lock():",
    "raise SystemExit(75) from error",
    "E2E self-test already running:",
):
    assert value in e2e_script, value

assert e2e_script.count(
    "def exclusive_run_lock()"
) == 1

assert e2e_script.count(
    "with exclusive_run_lock():"
) == 1

print("Monitoring E2E exclusive lock: OK")
print("Monitoring E2E parallel-run rejection: OK")
print("Monitoring E2E lock exit code: 75")

# v3.31 E2E JSON reporting

report_ignore_path = (
    ROOT
    / "monitoring/e2e-reports/.gitignore"
)

assert report_ignore_path.is_file()

report_ignore = report_ignore_path.read_text(
    encoding="utf-8"
)

assert "*" in report_ignore.splitlines()
assert "!.gitignore" in report_ignore.splitlines()

for value in (
    "SIGNALAI_E2E_REPORT_DIR",
    "SIGNALAI_E2E_REPORT_FILE",
    "SIGNALAI_E2E_HISTORY_FILE",
    "DEFAULT_HISTORY_LIMIT = 20",
    "def atomic_write_json(",
    "def persist_report(",
    "def build_report(",
    '"schema_version": 1',
    '"status": status',
    '"runtime_rule_removed":',
    '"notifications_total":',
    '"failures_total":',
    '"--report-file"',
    '"--history-file"',
    '"--history-limit"',
    'status="SUCCESS"',
    'status="FAILURE"',
    "JSON report:",
    "JSON history:",
):
    assert value in e2e_script, value

assert e2e_script.count(
    "with exclusive_run_lock():"
) == 1

print("Monitoring E2E JSON report: OK")
print("Monitoring E2E bounded history: 20")
print("Monitoring E2E report ignore rules: OK")
print("Monitoring E2E success/failure schema: OK")

# v3.31 E2E reports documentation

for value in (
    '"--report-file and --history-file "',
    '"must be different"',
    "args.report_file.resolve()",
    "args.history_file.resolve()",
):
    assert value in e2e_script, value

for value in (
    "## E2E parallel execution and JSON reports",
    "/tmp/signalai-monitoring-e2e.lock",
    "SIGNALAI_E2E_LOCK_FILE",
    "monitoring/e2e-reports/latest.json",
    "monitoring/e2e-reports/history.json",
    "--report-file",
    "--history-file",
    "--history-limit 20",
    "SIGNALAI_E2E_REPORT_DIR",
    "SIGNALAI_E2E_REPORT_FILE",
    "SIGNALAI_E2E_HISTORY_FILE",
    "SUCCESS или FAILURE",
    "Report file и history file должны быть разными",
):
    assert value in readme, value

print("Monitoring E2E report path validation: OK")
print("Monitoring E2E JSON report documentation: OK")
print("Monitoring E2E lock documentation: OK")

# v3.32 E2E Prometheus exporter

e2e_exporter_path = (
    ROOT
    / "monitoring/e2e_exporter.py"
)

e2e_exporter_test_path = (
    ROOT
    / "monitoring/test_e2e_exporter.py"
)

assert e2e_exporter_path.is_file()
assert e2e_exporter_path.stat().st_size > 0
assert e2e_exporter_path.stat().st_mode & 0o111

assert e2e_exporter_test_path.is_file()
assert e2e_exporter_test_path.stat().st_size > 0

e2e_exporter = e2e_exporter_path.read_text(
    encoding="utf-8"
)

e2e_exporter_tree = ast.parse(
    e2e_exporter
)

e2e_exporter_string_literals = "\n".join(
    node.value
    for node in ast.walk(
        e2e_exporter_tree
    )
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
    )
)

e2e_exporter_search_text = (
    e2e_exporter
    + "\n"
    + e2e_exporter_string_literals
)

for value in (
    "PROMETHEUS_CONTENT_TYPE",
    "def render_metrics(",
    "ThreadingHTTPServer",
    'self.path == "/metrics"',
    'self.path == "/-/ready"',
    "signalai_e2e_exporter_ready",
    "signalai_e2e_report_present",
    "signalai_e2e_report_valid",
    "signalai_e2e_last_run_status",
    "signalai_e2e_last_run_age_seconds",
    "signalai_e2e_last_run_duration_seconds",
    "signalai_e2e_last_run_runtime_rule_removed",
    "signalai_e2e_last_run_telegram_notifications",
    "signalai_e2e_last_run_telegram_failures",
    "signalai_e2e_history_entries",
    "signalai_e2e_history_runs",
):
    assert value in e2e_exporter_search_text, value

for value in (
    "  e2e-exporter:",
    "image: python:3.12-slim",
    "${E2E_EXPORTER_PORT:-9102}:9102",
    "./monitoring/e2e_exporter.py:"
    "/opt/signalai/e2e_exporter.py:ro",
    "./monitoring/e2e-reports:/data:ro",
):
    assert value in compose, value

for value in (
    "job_name: signalai-e2e",
    "metrics_path: /metrics",
    "e2e-exporter:9102",
    "service: signalai-e2e-exporter",
    "component: monitoring-e2e",
):
    assert value in prometheus, value

print("Monitoring E2E exporter script: OK")
print("Monitoring E2E exporter executable mode: OK")
print("Monitoring E2E exporter tests: OK")
print("Monitoring E2E exporter Compose service: OK")
print("Monitoring E2E Prometheus scrape job: OK")

# v3.32 E2E Grafana dashboard

e2e_dashboard_titles = {
    "Monitoring E2E Operations",
    "E2E Metrics Target",
    "Latest E2E Result",
    "Latest E2E Age",
    "Latest E2E Duration",
    "Runtime Rule Cleanup",
    "Telegram Failures at Last Run",
    "E2E Status History",
    "E2E Timing History",
}

assert (
    e2e_dashboard_titles
    <= dashboard_titles
)

for metric in (
    "signalai_e2e_last_run_status",
    "signalai_e2e_last_run_age_seconds",
    "signalai_e2e_last_run_duration_seconds",
    "signalai_e2e_last_run_runtime_rule_removed",
    "signalai_e2e_last_run_telegram_failures",
    "signalai_e2e_history_runs",
    "signalai_e2e_history_entries",
    "signalai_e2e_last_run_timeout_seconds",
):
    assert any(
        metric in expression
        for expression in expressions
    ), metric

assert len(dashboard["panels"]) == 39
assert dashboard["version"] >= 3

panel_ids = [
    panel["id"]
    for panel in dashboard["panels"]
]

assert len(panel_ids) == len(set(panel_ids))

print("Monitoring E2E Grafana panels: 9")
print("Monitoring E2E dashboard metrics: OK")
print("Total dashboard panels: 39")

# v3.32 E2E Prometheus alerts

e2e_alerts_path = (
    ROOT
    / "monitoring/prometheus/rules/"
    "e2e-alerts.yml"
)

assert e2e_alerts_path.is_file()
assert e2e_alerts_path.stat().st_size > 0

e2e_alerts = e2e_alerts_path.read_text(
    encoding="utf-8"
)

expected_e2e_alerts = (
    "SignalAIE2EMetricsTargetDown",
    "SignalAIE2ELatestReportMissing",
    "SignalAIE2ELatestReportInvalid",
    "SignalAIE2ELastRunFailed",
    "SignalAIE2ELastRunStale",
    "SignalAIE2ERuntimeRuleCleanupFailed",
)

for alert_name in expected_e2e_alerts:
    assert (
        f"alert: {alert_name}"
        in e2e_alerts
    ), alert_name

assert (
    e2e_alerts.count("      - alert: ")
    == 6
)

for value in (
    'up{job="signalai-e2e"} == 0',
    "signalai_e2e_report_present",
    "signalai_e2e_report_valid",
    "signalai_e2e_last_run_status",
    'status="FAILURE"',
    "signalai_e2e_last_run_age_seconds",
    "> 86400",
    (
        "signalai_e2e_last_run_"
        "runtime_rule_removed"
    ),
    "severity: critical",
    "severity: warning",
    "component: monitoring-e2e",
):
    assert value in e2e_alerts, value

for value in (
    "## E2E Prometheus exporter",
    "http://localhost:9102/-/ready",
    "http://localhost:9102/metrics",
    "signalai-e2e",
    "Monitoring E2E Operations",
    "## E2E Prometheus alerts",
    "monitoring/prometheus/rules/e2e-alerts.yml",
    "SignalAIE2EMetricsTargetDown",
    "SignalAIE2ELatestReportMissing",
    "SignalAIE2ELatestReportInvalid",
    "SignalAIE2ELastRunFailed",
    "SignalAIE2ELastRunStale",
    "SignalAIE2ERuntimeRuleCleanupFailed",
    "старше 24 часов",
):
    assert value in readme, value

print("Monitoring E2E Prometheus alerts: 6")
print("Monitoring E2E stale threshold: 24h")
print("Monitoring E2E exporter documentation: OK")
print("Monitoring E2E alert documentation: OK")
