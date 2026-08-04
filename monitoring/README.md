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


## Severity routing

Alertmanager направляет уведомления в Telegram с разными
интервалами в зависимости от severity.

Critical:

- group wait: 5 секунд
- group interval: 2 минуты
- repeat interval: 1 час
- receiver: signalai-telegram-critical

Warning:

- group wait: 30 секунд
- group interval: 10 минут
- repeat interval: 4 часа
- receiver: signalai-telegram-warning

Info и неизвестные значения severity:

- group wait: 2 минуты
- group interval: 30 минут
- repeat interval: 12 часов
- receiver: signalai-telegram-info

## Inhibition rules

Вторичные уведомления подавляются, когда активно более важное
связанное событие.

Настроены следующие правила:

- недоступный metrics target подавляет warning/info scheduler alerts;
- NOT_READY подавляет stopping и consecutive-failure alerts;
- failed cycle подавляет consecutive-failure alert.

Inhibition действует только при совпадении связанных labels,
указанных в конфигурации Alertmanager.

## Управление silences

Helper для управления silences:

    monitoring/alertmanager/silence.sh

Создание silence на 30 минут:

    ./monitoring/alertmanager/silence.sh add 30m       "Scheduler maintenance"       'alertname=~SignalAIScheduler.*'

Просмотр активных scheduler silences:

    ./monitoring/alertmanager/silence.sh list       component=scheduler

Получение только Silence ID:

    ./monitoring/alertmanager/silence.sh ids       component=scheduler

Завершение silence:

    ./monitoring/alertmanager/silence.sh expire       <silence-id>

Автор по умолчанию:

    SignalAI operator

Его можно изменить переменной окружения:

    SILENCE_AUTHOR="Vitalii"       ./monitoring/alertmanager/silence.sh add 30m       "Scheduler maintenance"       component=scheduler

Alertmanager должен быть запущен до использования helper.


## Мониторинг Alertmanager

Prometheus собирает внутренние метрики Alertmanager через job:

    signalai-alertmanager

Endpoint внутри Docker network:

    http://alertmanager:9093/metrics

Alertmanager Operations в Grafana показывает:

- доступность Alertmanager metrics target;
- успешность последней загрузки конфигурации;
- количество участников Alertmanager cluster;
- активные и подавленные alerts;
- активные silences;
- Telegram notifications и ошибки доставки;
- firing alerts самого Alertmanager.

Для Alertmanager настроены девять Prometheus alert rules:

- недоступность metrics endpoint;
- ошибка загрузки конфигурации;
- ошибка Telegram notification;
- наличие unprocessed alerts;
- получение invalid alerts;
- достижение лимита aggregation groups;
- длительно активные silences;
- длительно suppressed alerts;
- неожиданное количество cluster members.

Rules находятся в файле:

    monitoring/prometheus/rules/alertmanager-alerts.yml

Alertmanager dashboard является частью:

    SignalAI Scheduler Operations

UID dashboard:

    signalai-scheduler-ops

## Остановка

    docker compose --profile monitoring stop alertmanager prometheus grafana

Данные сохраняются в именованных Docker volumes:

- prometheus_data
- alertmanager_data
- grafana_data
