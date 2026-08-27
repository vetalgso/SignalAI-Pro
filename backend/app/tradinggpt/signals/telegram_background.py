from __future__ import annotations

import asyncio

from app.core.config import settings
from app.database.session import (
    SessionLocal,
    engine,
)
from app.tradinggpt.scheduler.background_loop import (
    SchedulerBackgroundLoop,
)
from app.tradinggpt.scheduler.distributed_lock import (
    PostgresAdvisorySchedulerLock,
)

from .telegram_delivery_repository import (
    TelegramDeliveryRepository,
)
from .telegram_dispatcher import (
    TelegramSignalDispatcher,
)
from .telegram_publisher import (
    TelegramSignalPublisher,
)


def _failure_reason(
    result: dict[str, object],
) -> str:
    existing = result.get("reason")

    if existing:
        return str(existing)

    errors = result.get("errors")

    if isinstance(errors, list):
        reasons = []

        for item in errors:
            if isinstance(item, dict):
                reason = item.get("reason")

                if reason:
                    reasons.append(str(reason))

        if reasons:
            return "; ".join(reasons[:10])

    return (
        "Telegram signal delivery "
        "batch did not complete."
    )


def run_telegram_signal_background_tick(
) -> dict[str, object]:
    if not settings.telegram_signal_enabled:
        return {
            "action": "SKIPPED_DISABLED",
            "reason": (
                "Telegram signal delivery "
                "is disabled."
            ),
        }

    if not (
        settings.telegram_signal_bot_token
        and settings.telegram_signal_chat_id
    ):
        return {
            "action": "FAILED",
            "reason": (
                "Telegram signal credentials "
                "are not configured."
            ),
        }

    distributed_lock = (
        PostgresAdvisorySchedulerLock(
            engine=engine,
            lock_key=(
                settings
                .telegram_signal_advisory_lock_key
            ),
        )
    )
    acquired = False

    try:
        acquired = (
            distributed_lock.try_acquire()
        )

        if not acquired:
            return {
                "action": "SKIPPED_LOCKED",
                "reason": (
                    "Another Telegram signal "
                    "dispatcher holds the lock."
                ),
            }

        with SessionLocal() as session:
            publisher = TelegramSignalPublisher(
                enabled=True,
                bot_token=(
                    settings
                    .telegram_signal_bot_token
                ),
                chat_id=(
                    settings
                    .telegram_signal_chat_id
                ),
                timeout_seconds=(
                    settings
                    .telegram_signal_timeout_seconds
                ),
            )

            dispatcher = TelegramSignalDispatcher(
                repository=(
                    TelegramDeliveryRepository(
                        session
                    )
                ),
                publisher=publisher,
                batch_size=(
                    settings
                    .telegram_signal_batch_size
                ),
                max_attempts=(
                    settings
                    .telegram_signal_max_attempts
                ),
                retry_base_seconds=(
                    settings
                    .telegram_signal_retry_base_seconds
                ),
                processing_lease_seconds=(
                    settings
                    .telegram_signal_processing_lease_seconds
                ),
            )

            result = asyncio.run(
                dispatcher.dispatch_once()
            )

            if result.get("action") in {
                "FAILED",
                "PARTIAL",
            }:
                result.setdefault(
                    "reason",
                    _failure_reason(result),
                )

            return result
    finally:
        if acquired:
            distributed_lock.release()


telegram_signal_background_loop = (
    SchedulerBackgroundLoop(
        tick_callback=(
            run_telegram_signal_background_tick
        ),
        poll_interval_seconds=(
            settings
            .telegram_signal_dispatch_poll_seconds
        ),
        task_name=(
            "tradinggpt-telegram-"
            "signal-delivery-loop"
        ),
        failure_actions=frozenset(
            {
                "FAILED",
                "PARTIAL",
            }
        ),
    )
)
