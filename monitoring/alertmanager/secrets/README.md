# Alertmanager Telegram Secrets

Этот каталог содержит локальные credentials Telegram.

Не добавляйте реальные значения в Git.

Необходимые локальные файлы:

- telegram_bot_token
- telegram_chat_id

После создания файлов:

    chmod 644 telegram_bot_token telegram_chat_id

После изменения значений пересоздайте контейнер:

    docker compose --profile monitoring up -d \
      --force-recreate alertmanager
