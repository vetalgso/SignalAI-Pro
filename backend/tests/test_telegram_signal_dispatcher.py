import asyncio
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from app.models.trading_signal import (
    TelegramSignalDelivery,
    TradingSignal,
)
from app.tradinggpt.signals.telegram_delivery_repository import (
    DELIVERY_FAILED,
    DELIVERY_PROCESSING,
    DELIVERY_RETRY,
    DELIVERY_SENT,
    DELIVERY_SKIPPED,
    TelegramDeliveryRepository,
)
from app.tradinggpt.signals.telegram_dispatcher import (
    TelegramSignalDispatcher,
)
from app.tradinggpt.signals.telegram_publisher import (
    TelegramPublishResult,
    TelegramSignalDeliveryError,
)


NOW = datetime(
    2026,
    8,
    27,
    12,
    0,
    tzinfo=timezone.utc,
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    TradingSignal.__table__.create(
        engine
    )
    TelegramSignalDelivery.__table__.create(
        engine
    )

    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
    session = factory()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def enqueue(
    db: Session,
    *,
    status: str = "ACTIVE",
    expires_at: datetime | None = None,
) -> TelegramSignalDelivery:
    signal = TradingSignal(
        fingerprint=(
            f"fingerprint-{status}-"
            f"{expires_at}"
        ),
        exchange="BINANCE",
        market_type="SPOT",
        symbol="BTCUSDT",
        timeframe="1H",
        side="LONG",
        strategy="TECHNICAL_CONFLUENCE_V1",
        status=status,
        confidence=Decimal("78.50"),
        risk_level="MEDIUM",
        risk_reward=Decimal("1.2500"),
        entry_min=Decimal("78000"),
        entry_max=Decimal("78100"),
        stop_loss=Decimal("77400"),
        take_profit_1=Decimal("78750"),
        take_profit_2=Decimal("79400"),
        take_profit_3=Decimal("80050"),
        current_price=Decimal("77980"),
        reasons=[
            (
                "Scanner and technical signal "
                "directions agree."
            ),
        ],
        metadata_payload={},
        source="MARKET_SCANNER",
        generated_at=NOW,
        expires_at=(
            expires_at
            or NOW + timedelta(hours=6)
        ),
        activated_at=NOW,
    )

    db.add(signal)
    db.flush()

    delivery = TelegramSignalDelivery(
        signal_id=signal.id,
        next_attempt_at=NOW,
    )

    db.add(delivery)
    db.commit()

    return delivery


class RecordingPublisher:
    def __init__(
        self,
        *,
        message_id: int = 321,
    ) -> None:
        self.message_id = message_id
        self.signal_ids: list[int] = []

    async def publish(
        self,
        signal: TradingSignal,
    ) -> TelegramPublishResult:
        self.signal_ids.append(signal.id)

        return TelegramPublishResult(
            delivered=True,
            reason="DELIVERED",
            message_id=self.message_id,
        )


class FailingPublisher:
    async def publish(
        self,
        _: TradingSignal,
    ) -> TelegramPublishResult:
        raise TelegramSignalDeliveryError(
            "Temporary Telegram failure."
        )


def test_repository_claims_due_delivery(
    db: Session,
) -> None:
    delivery = enqueue(db)
    repository = TelegramDeliveryRepository(
        db
    )

    jobs = repository.claim_due(
        now=NOW,
        limit=10,
        max_attempts=5,
    )

    assert len(jobs) == 1
    assert jobs[0].delivery.id == delivery.id
    assert delivery.status == DELIVERY_PROCESSING
    assert delivery.attempt_count == 1
    assert delivery.locked_at == NOW


def test_dispatcher_marks_sent(
    db: Session,
) -> None:
    delivery = enqueue(db)
    publisher = RecordingPublisher(
        message_id=654
    )

    result = asyncio.run(
        TelegramSignalDispatcher(
            repository=(
                TelegramDeliveryRepository(db)
            ),
            publisher=publisher,
            clock=lambda: NOW,
        ).dispatch_once()
    )

    assert result["action"] == "COMPLETED"
    assert result["sent"] == 1
    assert publisher.signal_ids

    db.refresh(delivery)

    assert delivery.status == DELIVERY_SENT
    assert delivery.telegram_message_id == 654
    assert delivery.sent_at is not None

    sent_at = delivery.sent_at

    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(
            tzinfo=timezone.utc
        )

    assert (
        sent_at.astimezone(timezone.utc)
        == NOW
    )
    assert delivery.locked_at is None


def test_dispatcher_skips_expired_signal(
    db: Session,
) -> None:
    delivery = enqueue(
        db,
        expires_at=(
            NOW - timedelta(seconds=1)
        ),
    )
    publisher = RecordingPublisher()

    result = asyncio.run(
        TelegramSignalDispatcher(
            repository=(
                TelegramDeliveryRepository(db)
            ),
            publisher=publisher,
            clock=lambda: NOW,
        ).dispatch_once()
    )

    assert result["skipped"] == 1
    assert publisher.signal_ids == []

    db.refresh(delivery)

    assert delivery.status == DELIVERY_SKIPPED
    assert "expired" in delivery.last_error.lower()


def test_dispatcher_retries_then_fails(
    db: Session,
) -> None:
    delivery = enqueue(db)
    repository = TelegramDeliveryRepository(
        db
    )

    first = asyncio.run(
        TelegramSignalDispatcher(
            repository=repository,
            publisher=FailingPublisher(),
            max_attempts=2,
            retry_base_seconds=10,
            clock=lambda: NOW,
        ).dispatch_once()
    )

    assert first["retried"] == 1
    assert delivery.status == DELIVERY_RETRY
    assert delivery.attempt_count == 1
    assert delivery.next_attempt_at == (
        NOW + timedelta(seconds=10)
    )

    later = NOW + timedelta(seconds=11)

    second = asyncio.run(
        TelegramSignalDispatcher(
            repository=repository,
            publisher=FailingPublisher(),
            max_attempts=2,
            retry_base_seconds=10,
            clock=lambda: later,
        ).dispatch_once()
    )

    assert second["failed"] == 1
    assert delivery.status == DELIVERY_FAILED
    assert delivery.attempt_count == 2
    assert delivery.locked_at is None


def test_dispatcher_recovers_stale_job(
    db: Session,
) -> None:
    delivery = enqueue(db)
    delivery.status = DELIVERY_PROCESSING
    delivery.attempt_count = 1
    delivery.locked_at = (
        NOW - timedelta(minutes=10)
    )
    db.commit()

    publisher = RecordingPublisher()

    result = asyncio.run(
        TelegramSignalDispatcher(
            repository=(
                TelegramDeliveryRepository(db)
            ),
            publisher=publisher,
            max_attempts=5,
            processing_lease_seconds=300,
            clock=lambda: NOW,
        ).dispatch_once()
    )

    assert result["recovered"] == 1
    assert result["sent"] == 1
    assert delivery.status == DELIVERY_SENT
    assert delivery.attempt_count == 2
