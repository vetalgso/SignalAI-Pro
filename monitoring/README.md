# SignalAI Monitoring Stack

Monitoring запускается отдельным Docker Compose-профилем
и не влияет на обычный запуск SignalAI-Pro.

## Запуск

    docker compose --profile monitoring up -d

## Интерфейсы

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001
- Alertmanager: http://localhost:9093
- Dashboard: SignalAI Scheduler Operations

Локальные учётные данные Grafana по умолчанию:

- username: admin
- password: signalai-local

Поддерживаемые переменные окружения:

- PROMETHEUS_PORT
- GRAFANA_PORT
- GRAFANA_ADMIN_USER
- GRAFANA_ADMIN_PASSWORD
- ALERTMANAGER_PORT

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


## Alertmanager и Telegram

Prometheus передаёт сработавшие правила в Alertmanager:

    http://alertmanager:9093

Конфигурация Alertmanager:

    monitoring/alertmanager/alertmanager.yml

Telegram-шаблон:

    monitoring/alertmanager/templates/telegram.tmpl

Локальные Telegram credentials хранятся в файлах:

    monitoring/alertmanager/secrets/telegram_bot_token
    monitoring/alertmanager/secrets/telegram_chat_id

Эти файлы исключены из Git. Токен и Chat ID нельзя добавлять
в commits, логи или документацию.

Для создания файлов:

    printf '%s\n' '<BOT_TOKEN>' > monitoring/alertmanager/secrets/telegram_bot_token
    printf '%s\n' '<CHAT_ID>' > monitoring/alertmanager/secrets/telegram_chat_id
    chmod 644 monitoring/alertmanager/secrets/telegram_bot_token
    chmod 644 monitoring/alertmanager/secrets/telegram_chat_id

После изменения credentials необходимо пересоздать Alertmanager:

    docker compose --profile monitoring up -d --force-recreate alertmanager

Проверка конфигурации:

    docker compose --profile monitoring run --rm --no-deps \
      --entrypoint amtool alertmanager \
      check-config /etc/alertmanager/alertmanager.yml

Alertmanager отправляет как сработавшие, так и восстановленные
уведомления благодаря параметру send_resolved.

## Остановка

    docker compose --profile monitoring stop alertmanager prometheus grafana

Данные сохраняются в именованных Docker volumes:

- prometheus_data
- alertmanager_data
- grafana_data
