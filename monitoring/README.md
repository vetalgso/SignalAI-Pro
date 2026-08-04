# SignalAI Monitoring Stack

Monitoring запускается отдельным Docker Compose-профилем
и не влияет на обычный запуск SignalAI-Pro.

## Запуск

    docker compose --profile monitoring up -d

## Интерфейсы

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001
- Dashboard: SignalAI Scheduler Operations

Локальные учётные данные Grafana по умолчанию:

- username: admin
- password: signalai-local

Поддерживаемые переменные окружения:

- PROMETHEUS_PORT
- GRAFANA_PORT
- GRAFANA_ADMIN_USER
- GRAFANA_ADMIN_PASSWORD

## Prometheus

Scheduler metrics endpoint:

    http://api:8000/api/v3/scheduler/metrics

Scrape-конфигурация:

    monitoring/prometheus/prometheus.yml

Alert rules:

    monitoring/prometheus/rules/scheduler-alerts.yml

Проверка конфигурации:

    docker compose --profile monitoring run --rm --no-deps \
      --entrypoint promtool prometheus \
      check config /etc/prometheus/prometheus.yml

## Grafana

Provisioning и dashboard находятся в каталогах:

    monitoring/grafana/provisioning
    monitoring/grafana/dashboards

Dashboard UID:

    signalai-scheduler-ops

## Остановка

    docker compose --profile monitoring stop prometheus grafana

Данные сохраняются в именованных Docker volumes:

- prometheus_data
- grafana_data
