from __future__ import annotations

from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
)
from typing import Final

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.trading_signal import (
    TelegramSignalDelivery,
    TradingSignal,
    TradingSignalEvent,
)


DELIVERY_PENDING: Final = "PENDING"
DELIVERY_PROCESSING: Final = "PROCESSING"
DELIVERY_RETRY: Final = "RETRY"
DELIVERY_SENT: Final = "SENT"
DELIVERY_SKIPPED: Final = "SKIPPED"
DELIVERY_FAILED: Final = "FAILED"

MAX_ERROR_LENGTH: Final = 1000


@dataclass(frozen=True)
class TelegramDeliveryJob:
    delivery: TelegramSignalDelivery
    signal: TradingSignal
    event: TradingSignalEvent | None


class TelegramDeliveryRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    @staticmethod
    def _error(value: str) -> str:
        normalized = value.strip()

        return (
            normalized[:MAX_ERROR_LENGTH]
            or "Unknown delivery error."
        )

    def recover_stale(
        self,
        *,
        now: datetime,
        lease_seconds: float,
        max_attempts: int,
    ) -> int:
        if lease_seconds <= 0:
            raise ValueError(
                "Delivery lease must be positive."
            )

        stale_before = (
            now
            - timedelta(
                seconds=lease_seconds
            )
        )

        statement = (
            select(TelegramSignalDelivery)
            .where(
                TelegramSignalDelivery.status
                == DELIVERY_PROCESSING
            )
            .where(
                or_(
                    TelegramSignalDelivery
                    .locked_at
                    .is_(None),
                    TelegramSignalDelivery
                    .locked_at
                    <= stale_before,
                )
            )
            .with_for_update(
                skip_locked=True
            )
        )

        deliveries = list(
            self.session.scalars(
                statement
            ).all()
        )

        for delivery in deliveries:
            delivery.locked_at = None
            delivery.updated_at = now

            if (
                delivery.attempt_count
                >= max_attempts
            ):
                delivery.status = DELIVERY_FAILED
                delivery.last_error = (
                    "Delivery processing lease "
                    "expired after maximum attempts."
                )
            else:
                delivery.status = DELIVERY_RETRY
                delivery.next_attempt_at = now
                delivery.last_error = (
                    "Recovered stale processing "
                    "delivery."
                )

        if deliveries:
            self.session.commit()

        return len(deliveries)

    def fail_exhausted(
        self,
        *,
        now: datetime,
        max_attempts: int,
    ) -> int:
        statement = (
            select(TelegramSignalDelivery)
            .where(
                TelegramSignalDelivery.status.in_(
                    (
                        DELIVERY_PENDING,
                        DELIVERY_RETRY,
                    )
                )
            )
            .where(
                TelegramSignalDelivery
                .attempt_count
                >= max_attempts
            )
            .with_for_update(
                skip_locked=True
            )
        )

        deliveries = list(
            self.session.scalars(
                statement
            ).all()
        )

        for delivery in deliveries:
            delivery.status = DELIVERY_FAILED
            delivery.locked_at = None
            delivery.updated_at = now
            delivery.last_error = (
                delivery.last_error
                or (
                    "Telegram delivery exceeded "
                    "maximum attempts."
                )
            )

        if deliveries:
            self.session.commit()

        return len(deliveries)

    def claim_due(
        self,
        *,
        now: datetime,
        limit: int,
        max_attempts: int,
    ) -> list[TelegramDeliveryJob]:
        if limit <= 0:
            raise ValueError(
                "Delivery batch limit "
                "must be positive."
            )

        statement = (
            select(
                TelegramSignalDelivery,
                TradingSignal,
                TradingSignalEvent,
            )
            .join(
                TradingSignal,
                TradingSignal.id
                == TelegramSignalDelivery.signal_id,
            )
            .outerjoin(
                TradingSignalEvent,
                TradingSignalEvent.id
                == TelegramSignalDelivery.event_id,
            )
            .where(
                TelegramSignalDelivery.status.in_(
                    (
                        DELIVERY_PENDING,
                        DELIVERY_RETRY,
                    )
                )
            )
            .where(
                TelegramSignalDelivery
                .next_attempt_at
                <= now
            )
            .where(
                TelegramSignalDelivery
                .attempt_count
                < max_attempts
            )
            .order_by(
                TelegramSignalDelivery
                .next_attempt_at.asc(),
                TelegramSignalDelivery.id.asc(),
            )
            .limit(limit)
            .with_for_update(
                of=TelegramSignalDelivery,
                skip_locked=True,
            )
        )

        rows = self.session.execute(
            statement
        ).all()

        jobs: list[TelegramDeliveryJob] = []

        for delivery, signal, event in rows:
            delivery.status = (
                DELIVERY_PROCESSING
            )
            delivery.attempt_count += 1
            delivery.locked_at = now
            delivery.updated_at = now
            delivery.last_error = None

            jobs.append(
                TelegramDeliveryJob(
                    delivery=delivery,
                    signal=signal,
                    event=event,
                )
            )

        if jobs:
            self.session.commit()

        return jobs

    def mark_sent(
        self,
        *,
        delivery: TelegramSignalDelivery,
        message_id: int,
        now: datetime,
    ) -> None:
        delivery.status = DELIVERY_SENT
        delivery.telegram_message_id = (
            message_id
        )
        delivery.sent_at = now
        delivery.locked_at = None
        delivery.last_error = None
        delivery.updated_at = now

        self.session.commit()

    def mark_skipped(
        self,
        *,
        delivery: TelegramSignalDelivery,
        reason: str,
        now: datetime,
    ) -> None:
        delivery.status = DELIVERY_SKIPPED
        delivery.locked_at = None
        delivery.last_error = self._error(
            reason
        )
        delivery.updated_at = now

        self.session.commit()

    def mark_failed(
        self,
        *,
        delivery: TelegramSignalDelivery,
        reason: str,
        now: datetime,
    ) -> None:
        delivery.status = DELIVERY_FAILED
        delivery.locked_at = None
        delivery.last_error = self._error(
            reason
        )
        delivery.updated_at = now

        self.session.commit()

    def mark_retry(
        self,
        *,
        delivery: TelegramSignalDelivery,
        reason: str,
        now: datetime,
        delay_seconds: float,
        max_attempts: int,
    ) -> str:
        delivery.locked_at = None
        delivery.last_error = self._error(
            reason
        )
        delivery.updated_at = now

        if (
            delivery.attempt_count
            >= max_attempts
        ):
            delivery.status = DELIVERY_FAILED
            self.session.commit()
            return DELIVERY_FAILED

        delivery.status = DELIVERY_RETRY
        delivery.next_attempt_at = (
            now
            + timedelta(
                seconds=delay_seconds
            )
        )

        self.session.commit()
        return DELIVERY_RETRY
