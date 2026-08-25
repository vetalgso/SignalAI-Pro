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


## Monitoring E2E self-test

Полный тест цепочки мониторинга запускается командой:

    ./monitoring/e2e_self_test.py --timeout 90

Тест проверяет цепочку:

    Prometheus -> Alertmanager -> Telegram

Во время запуска создаётся временный Prometheus alert rule:

    e2e-self-test.runtime.yml

Он генерирует уникальный critical alert с label:

    self_test="true"

Alertmanager направляет такой alert через ускоренный маршрут:

- receiver: signalai-telegram-critical;
- group wait: 1 секунда;
- group interval: 5 секунд;
- send resolved: enabled.

Self-test автоматически проверяет:

- загрузку временного Prometheus rule;
- переход alert в firing;
- получение alert в Alertmanager;
- успешную Telegram firing notification;
- переход alert в resolved;
- успешную Telegram resolved notification;
- отсутствие роста Telegram failure counter;
- удаление временного rule после завершения.

За один успешный запуск в Telegram приходят два сообщения:

- SIGNALAI ALERT;
- SIGNALAI RESOLVED.

Runtime rule исключён из Git через:

    monitoring/prometheus/rules/.gitignore

Self-test отправляет реальные сообщения в настроенный Telegram-чат.
Перед запуском должны работать Prometheus и Alertmanager, а Telegram
secrets должны находиться в локальном каталоге Alertmanager secrets.


## E2E parallel execution and JSON reports

Одновременно может выполняться только один monitoring E2E self-test.

Для межпроцессной блокировки используется файл:

    monitoring/e2e-reports/e2e-self-test.lock

Если другой self-test уже работает, новый запуск завершается с кодом:

    75

Сообщение об ошибке содержит metadata владельца lock:

- PID;
- hostname;
- время начала запуска.

Путь lock-файла можно переопределить переменной:

    SIGNALAI_E2E_LOCK_FILE

После каждого выполненного теста создаётся latest JSON report:

    monitoring/e2e-reports/latest.json

История запусков сохраняется в:

    monitoring/e2e-reports/history.json

По умолчанию сохраняются последние 20 результатов. Пути и лимит можно
переопределить параметрами:

    ./monitoring/e2e_self_test.py \
      --timeout 90 \
      --report-file monitoring/e2e-reports/latest.json \
      --history-file monitoring/e2e-reports/history.json \
      --history-limit 20

Также поддерживаются переменные окружения:

- SIGNALAI_E2E_REPORT_DIR;
- SIGNALAI_E2E_REPORT_FILE;
- SIGNALAI_E2E_HISTORY_FILE.

Latest report и history записываются атомарно. JSON report содержит:

- schema version;
- SUCCESS или FAILURE;
- уникальный run ID;
- время начала и завершения;
- продолжительность теста;
- timeout;
- PID и hostname;
- состояние cleanup временного Prometheus rule;
- Telegram notifications total;
- Telegram failures total;
- тип и сообщение ошибки при неуспешном запуске.

Report file и history file должны быть разными файлами.

Каталог runtime-отчётов исключён из Git. В репозитории хранится только:

    monitoring/e2e-reports/.gitignore



## Periodic E2E runner

Compose service `e2e-runner` автоматически запускает monitoring E2E
self-test по расписанию.

По умолчанию используются значения:

- startup delay: 300 секунд;
- интервал после SUCCESS: 86400 секунд;
- retry после FAILURE или занятого lock: 900 секунд;
- timeout одной фазы self-test: 90 секунд;
- timeout процесса: 600 секунд;
- размер JSON history: 20 запусков.

Настройка выполняется переменными:

- E2E_RUNNER_STARTUP_DELAY_SECONDS;
- E2E_RUNNER_INTERVAL_SECONDS;
- E2E_RUNNER_RETRY_DELAY_SECONDS;
- E2E_RUNNER_SELF_TEST_TIMEOUT_SECONDS;
- E2E_RUNNER_PROCESS_TIMEOUT_SECONDS;
- E2E_RUNNER_HISTORY_LIMIT.

Состояние расписания записывается атомарно в:

    monitoring/e2e-reports/runner-state.json

State содержит:

- статус STARTING, WAITING, RUNNING, COMPLETED или STOPPED;
- время следующего запуска;
- последний результат SUCCESS, FAILURE или LOCKED;
- exit code и ошибку;
- счётчики запусков, успехов, ошибок и конфликтов lock;
- число последовательных ошибок;
- текущую конфигурацию runner.

Self-test внутри контейнера обращается к сервисам:

    http://prometheus:9090
    http://alertmanager:9093

Временный rule записывается в общий каталог Prometheus rules. Runner и
ручной host-запуск используют общий lock-файл в каталоге E2E reports.

Периодический запуск отправляет реальные firing и resolved сообщения в
Telegram. Для безопасной проверки сервиса без отправки сообщений можно
временно увеличить startup delay:

    E2E_RUNNER_STARTUP_DELAY_SECONDS=3600 \
      docker compose --profile monitoring up -d e2e-runner



### Periodic runner restart recovery

При старте periodic runner читает существующий `runner-state.json`.

Поведение после перезапуска:

- будущее время запуска в состоянии `WAITING` сохраняется;
- просроченное расписание выполняется без дополнительной задержки;
- счётчики запусков, успехов, ошибок и lock conflicts сохраняются;
- состояние `RUNNING` считается прерванным запуском;
- прерванный запуск получает exit code `125` и результат `FAILURE`;
- после прерванного запуска применяется обычный retry delay;
- повреждённый или несовместимый state безопасно сбрасывается.

Exporter публикует recovery-метрики:

- `signalai_e2e_runner_recovered`;
- `signalai_e2e_runner_restart_count`;
- `signalai_e2e_runner_recovery_reason`;
- `signalai_e2e_runner_process_started_timestamp_seconds`;
- `signalai_e2e_runner_recovered_timestamp_seconds`;
- `signalai_e2e_runner_interrupted_last_run`.

`signalai_e2e_runner_recovery_reason` использует только фиксированный
набор labels и не создаёт high-cardinality series.


Recovery observability включает дополнительные alerts:

- `SignalAIE2ERunnerInterruptedRun`;
- `SignalAIE2ERunnerRestartLoop`.

Первый alert обнаруживает восстановленный прерванный запуск. Второй
обнаруживает не менее трёх изменений restart counter за 15 минут.

Grafana-раздел `Periodic E2E Recovery` показывает:

- факт восстановления persistent state;
- причину восстановления;
- накопительный restart count;
- признак последнего прерванного запуска;
- историю recovery lifecycle.

### Periodic runner alerts and dashboard

Prometheus контролирует состояние автоматического runner через alerts:

- SignalAIE2ERunnerStateMissing;
- SignalAIE2ERunnerStateInvalid;
- SignalAIE2ERunnerStopped;
- SignalAIE2ERunnerLastRunFailed;
- SignalAIE2ERunnerConsecutiveFailures;
- SignalAIE2ERunnerScheduleOverdue.

`SignalAIE2ERunnerScheduleOverdue` срабатывает, если runner находится в
WAITING, но запланированное время запуска просрочено более чем на 15
минут.

Grafana dashboard содержит отдельный раздел:

    Periodic E2E Runner

В разделе отображаются:

- текущий статус runner;
- последний результат;
- время до следующего запуска;
- общее число запусков, успехов и ошибок;
- последовательные ошибки;
- конфликты межпроцессной блокировки;
- история статусов и результатов;
- история delay, длительности и возраста state.

## E2E Prometheus exporter

Monitoring E2E exporter преобразует runtime JSON-отчёты self-test в
Prometheus metrics.

Compose service:

    e2e-exporter

Локальные endpoints:

    http://localhost:9102/-/ready
    http://localhost:9102/metrics

Порт можно изменить переменной окружения:

    E2E_EXPORTER_PORT

Exporter читает файлы:

    monitoring/e2e-reports/latest.json
    monitoring/e2e-reports/history.json

Каталог подключается в контейнер только для чтения.

Prometheus scrape job:

    signalai-e2e

Основные метрики:

- signalai_e2e_exporter_ready;
- signalai_e2e_report_present;
- signalai_e2e_report_valid;
- signalai_e2e_last_run_status;
- signalai_e2e_last_run_age_seconds;
- signalai_e2e_last_run_duration_seconds;
- signalai_e2e_last_run_timeout_seconds;
- signalai_e2e_last_run_runtime_rule_removed;
- signalai_e2e_last_run_telegram_notifications;
- signalai_e2e_last_run_telegram_failures;
- signalai_e2e_history_entries;
- signalai_e2e_history_runs.


Exporter также читает `runner-state.json` и публикует состояние
периодического расписания без динамических high-cardinality labels.

Runner metrics включают:

- signalai_e2e_runner_state_present;
- signalai_e2e_runner_state_valid;
- signalai_e2e_runner_status;
- signalai_e2e_runner_last_result;
- signalai_e2e_runner_state_age_seconds;
- signalai_e2e_runner_next_run_timestamp_seconds;
- signalai_e2e_runner_next_run_delay_seconds;
- signalai_e2e_runner_last_duration_seconds;
- signalai_e2e_runner_last_exit_code;
- signalai_e2e_runner_runs_total;
- signalai_e2e_runner_successes_total;
- signalai_e2e_runner_failures_total;
- signalai_e2e_runner_lock_conflicts_total;
- signalai_e2e_runner_consecutive_failures;
- signalai_e2e_runner_config_interval_seconds;
- signalai_e2e_runner_config_retry_delay_seconds.

Grafana dashboard `signalai-scheduler-ops` содержит раздел:

    Monitoring E2E Operations

В разделе отображаются:

- доступность exporter;
- последний SUCCESS или FAILURE;
- возраст последней проверки;
- длительность проверки;
- результат cleanup временного rule;
- Telegram failures;
- история результатов и времени выполнения.

## E2E Prometheus alerts

Файл правил:

    monitoring/prometheus/rules/e2e-alerts.yml

Доступны alerts:

- SignalAIE2EMetricsTargetDown;
- SignalAIE2ELatestReportMissing;
- SignalAIE2ELatestReportInvalid;
- SignalAIE2ELastRunFailed;
- SignalAIE2ELastRunStale;
- SignalAIE2ERuntimeRuleCleanupFailed.

Alert `SignalAIE2ELastRunStale` срабатывает, если последний E2E-результат
старше 24 часов.

Critical alerts направляются через receiver:

    signalai-telegram-critical

Warning alerts направляются через receiver:

    signalai-telegram-warning

## Остановка

    docker compose --profile monitoring stop e2e-runner e2e-exporter alertmanager prometheus grafana

Данные сохраняются в именованных Docker volumes:

- prometheus_data
- alertmanager_data
- grafana_data

## Automatic order reconciliation monitoring

Prometheus read-only endpoint:

http://api:8000/api/v3/orders/reconciliation/metrics

Job `signalai-order-reconciliation` показывает
состояние worker, read-only invariant, итерации,
ошибки, длительность и возраст последнего тика.

Alerts находятся в `reconciliation-alerts.yml`.
Выключенный worker не создаёт ложных alerts.

Grafana dashboard UID:
`signalai-order-reconciliation`.

Мониторинг не отправляет и не отменяет ордера.
