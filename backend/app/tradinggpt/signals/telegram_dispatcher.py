from __future__ import annotations

from collections.abc import Callable
from datetime import (
    datetime,
    timezone,
)
from typing import Protocol

from app.models.trading_signal import (
    TradingSignal,
    TradingSignalEvent,
)

from .telegram_delivery_repository import (
    DELIVERY_FAILED,
    DELIVERY_RETRY,
    TelegramDeliveryRepository,
)
from .telegram_publisher import (
    TelegramPublishResult,
    TelegramSignalConfigurationError,
    TelegramSignalDeliveryError,
)


class SignalPublisher(Protocol):
    async def publish(
        self,
        signal: TradingSignal,
        *,
        delivery_type: str,
        event: TradingSignalEvent | None,
    ) -> TelegramPublishResult:
        ...


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware_utc(
    value: datetime,
) -> datetime:
    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


class TelegramSignalDispatcher:
    def __init__(
        self,
        *,
        repository: TelegramDeliveryRepository,
        publisher: SignalPublisher,
        batch_size: int = 20,
        max_attempts: int = 5,
        retry_base_seconds: float = 30.0,
        processing_lease_seconds: float = 300.0,
        clock: Callable[
            [],
            datetime,
        ] = utc_now,
    ) -> None:
        if batch_size <= 0:
            raise ValueError(
                "Dispatcher batch size "
                "must be positive."
            )

        if max_attempts <= 0:
            raise ValueError(
                "Dispatcher max attempts "
                "must be positive."
            )

        if retry_base_seconds <= 0:
            raise ValueError(
                "Retry delay must be positive."
            )

        if processing_lease_seconds <= 0:
            raise ValueError(
                "Processing lease must "
                "be positive."
            )

        self.repository = repository
        self.publisher = publisher
        self.batch_size = batch_size
        self.max_attempts = max_attempts
        self.retry_base_seconds = (
            retry_base_seconds
        )
        self.processing_lease_seconds = (
            processing_lease_seconds
        )
        self.clock = clock

    def _retry_delay(
        self,
        attempt_count: int,
    ) -> float:
        exponent = max(
            0,
            attempt_count - 1,
        )

        return min(
            self.retry_base_seconds
            * (2**exponent),
            3600.0,
        )

    async def dispatch_once(
        self,
    ) -> dict[str, object]:
        now = _aware_utc(
            self.clock()
        )

        recovered = (
            self.repository.recover_stale(
                now=now,
                lease_seconds=(
                    self.processing_lease_seconds
                ),
                max_attempts=(
                    self.max_attempts
                ),
            )
        )

        exhausted = (
            self.repository.fail_exhausted(
                now=now,
                max_attempts=(
                    self.max_attempts
                ),
            )
        )

        jobs = self.repository.claim_due(
            now=now,
            limit=self.batch_size,
            max_attempts=self.max_attempts,
        )

        sent = 0
        retried = 0
        skipped = 0
        failed = exhausted
        errors: list[
            dict[str, object]
        ] = []

        for job in jobs:
            delivery = job.delivery
            signal = job.signal
            event = job.event

            supported_types = {
                "SIGNAL_CREATED",
                "SIGNAL_STATUS_CHANGED",
            }

            if (
                delivery.delivery_type
                not in supported_types
            ):
                reason = (
                    "Unsupported Telegram delivery "
                    f"type: {delivery.delivery_type}."
                )
                self.repository.mark_failed(
                    delivery=delivery,
                    reason=reason,
                    now=now,
                )
                failed += 1
                errors.append({
                    "signal_id": signal.id,
                    "delivery_id": delivery.id,
                    "reason": reason,
                })
                continue

            if (
                delivery.delivery_type
                == "SIGNAL_STATUS_CHANGED"
                and event is None
            ):
                reason = (
                    "Lifecycle delivery has no "
                    "signal event."
                )
                self.repository.mark_failed(
                    delivery=delivery,
                    reason=reason,
                    now=now,
                )
                failed += 1
                errors.append({
                    "signal_id": signal.id,
                    "delivery_id": delivery.id,
                    "reason": reason,
                })
                continue

            if (
                delivery.delivery_type
                == "SIGNAL_CREATED"
                and signal.status != "ACTIVE"
            ):
                self.repository.mark_skipped(
                    delivery=delivery,
                    reason=(
                        "Signal is no longer active: "
                        f"{signal.status}."
                    ),
                    now=now,
                )
                skipped += 1
                continue

            if (
                delivery.delivery_type
                == "SIGNAL_CREATED"
                and signal.expires_at is not None
                and _aware_utc(
                    signal.expires_at
                )
                <= now
            ):
                self.repository.mark_skipped(
                    delivery=delivery,
                    reason=(
                        "Signal expired before "
                        "Telegram delivery."
                    ),
                    now=now,
                )
                skipped += 1
                continue

            try:
                result = await (
                    self.publisher.publish(
                        signal,
                        delivery_type=(
                            delivery.delivery_type
                        ),
                        event=event,
                    )
                )
            except (
                TelegramSignalConfigurationError
            ) as exc:
                reason = str(exc)

                self.repository.mark_failed(
                    delivery=delivery,
                    reason=reason,
                    now=now,
                )
                failed += 1
                errors.append(
                    {
                        "signal_id": signal.id,
                        "reason": reason,
                    }
                )
                continue
            except TelegramSignalDeliveryError as exc:
                reason = str(exc)

                status = (
                    self.repository.mark_retry(
                        delivery=delivery,
                        reason=reason,
                        now=now,
                        delay_seconds=(
                            self._retry_delay(
                                delivery
                                .attempt_count
                            )
                        ),
                        max_attempts=(
                            self.max_attempts
                        ),
                    )
                )

                if status == DELIVERY_RETRY:
                    retried += 1
                else:
                    failed += 1

                errors.append(
                    {
                        "signal_id": signal.id,
                        "reason": reason,
                    }
                )
                continue
            except Exception as exc:
                reason = (
                    "Unexpected publisher error: "
                    f"{type(exc).__name__}."
                )

                status = (
                    self.repository.mark_retry(
                        delivery=delivery,
                        reason=reason,
                        now=now,
                        delay_seconds=(
                            self._retry_delay(
                                delivery
                                .attempt_count
                            )
                        ),
                        max_attempts=(
                            self.max_attempts
                        ),
                    )
                )

                if status == DELIVERY_RETRY:
                    retried += 1
                else:
                    failed += 1

                errors.append(
                    {
                        "signal_id": signal.id,
                        "reason": reason,
                    }
                )
                continue

            if (
                not result.delivered
                or result.message_id is None
            ):
                status = (
                    self.repository.mark_retry(
                        delivery=delivery,
                        reason=(
                            "Publisher did not confirm "
                            "Telegram delivery."
                        ),
                        now=now,
                        delay_seconds=(
                            self._retry_delay(
                                delivery
                                .attempt_count
                            )
                        ),
                        max_attempts=(
                            self.max_attempts
                        ),
                    )
                )

                if status == DELIVERY_RETRY:
                    retried += 1
                else:
                    failed += 1

                continue

            self.repository.mark_sent(
                delivery=delivery,
                message_id=result.message_id,
                now=now,
            )
            sent += 1

        if failed and not (
            sent or retried or skipped
        ):
            action = "FAILED"
        elif failed or retried:
            action = "PARTIAL"
        elif jobs or recovered or exhausted:
            action = "COMPLETED"
        else:
            action = "IDLE"

        return {
            "action": action,
            "claimed": len(jobs),
            "sent": sent,
            "retried": retried,
            "skipped": skipped,
            "failed": failed,
            "recovered": recovered,
            "exhausted": exhausted,
            "errors": errors,
        }
