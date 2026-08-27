from __future__ import annotations

from datetime import (
    UTC,
    datetime,
    timedelta,
)
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from app.models.trading_signal import (
    TelegramSignalDelivery,
    TradingSignal,
    TradingSignalEvent,
)
from app.tradinggpt.signals.repository import (
    TradingSignalRepository,
)
from app.tradinggpt.signals.schemas import (
    SignalCreateRequest,
    SignalRiskLevel,
    SignalSide,
    SignalStatus,
    SignalTransitionRequest,
)
from app.tradinggpt.signals.service import (
    DuplicateSignalError,
    InvalidSignalTransitionError,
    TradingSignalService,
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

    TradingSignal.__table__.create(engine)
    TradingSignalEvent.__table__.create(
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


def make_request(
    **overrides: object,
) -> SignalCreateRequest:
    payload: dict[str, object] = {
        "exchange": "binance",
        "market_type": "futures",
        "symbol": "btcusdt",
        "timeframe": "1h",
        "side": "LONG",
        "strategy": "trend momentum",
        "confidence": Decimal("78.50"),
        "risk_level": "MEDIUM",
        "entry_min": Decimal("63900"),
        "entry_max": Decimal("64300"),
        "stop_loss": Decimal("62800"),
        "take_profit_1": Decimal("65500"),
        "take_profit_2": Decimal("67000"),
        "take_profit_3": Decimal("69000"),
        "current_price": Decimal("64100"),
        "reasons": [
            "Higher-timeframe trend",
            "Volume expansion",
        ],
        "source": "scanner",
        "generated_at": datetime(
            2026,
            8,
            4,
            18,
            15,
            tzinfo=UTC,
        ),
        "expires_at": datetime(
            2026,
            8,
            5,
            18,
            15,
            tzinfo=UTC,
        ),
    }

    payload.update(overrides)

    return SignalCreateRequest(
        **payload
    )


def make_service(
    db: Session,
) -> TradingSignalService:
    return TradingSignalService(
        TradingSignalRepository(db)
    )


def test_create_product_signal(
    db: Session,
) -> None:
    signal = make_service(db).create(
        make_request()
    )

    assert signal.id is not None
    assert signal.exchange == "BINANCE"
    assert signal.symbol == "BTCUSDT"
    assert signal.timeframe == "1H"
    assert signal.side == "LONG"
    assert signal.status == "ACTIVE"
    assert signal.risk_level == "MEDIUM"
    assert signal.risk_reward > 0
    assert len(signal.fingerprint) == 64

    events = (
        TradingSignalRepository(
            db
        ).list_events(signal.id)
    )

    assert len(events) == 1
    assert events[0].event_type == "CREATED"
    assert events[0].to_status == "ACTIVE"


def test_duplicate_signal_is_rejected(
    db: Session,
) -> None:
    service = make_service(db)
    first = service.create(
        make_request()
    )

    with pytest.raises(
        DuplicateSignalError
    ) as error:
        service.create(make_request())

    assert (
        error.value.existing_signal_id
        == first.id
    )


def test_signal_list_filters(
    db: Session,
) -> None:
    service = make_service(db)

    service.create(make_request())

    service.create(
        make_request(
            symbol="ETHUSDT",
            side=SignalSide.SHORT,
            strategy="breakdown",
            entry_min=Decimal("3400"),
            entry_max=Decimal("3420"),
            stop_loss=Decimal("3510"),
            take_profit_1=Decimal("3300"),
            take_profit_2=Decimal("3200"),
            take_profit_3=Decimal("3100"),
            generated_at=datetime(
                2026,
                8,
                4,
                19,
                15,
                tzinfo=UTC,
            ),
        )
    )

    items, total = service.list(
        exchange="BINANCE",
        symbol="BTCUSDT",
        timeframe=None,
        side="LONG",
        status="ACTIVE",
        risk_level="MEDIUM",
        min_confidence=Decimal("70"),
        limit=50,
        offset=0,
    )

    assert total == 1
    assert len(items) == 1
    assert items[0].symbol == "BTCUSDT"


def test_signal_lifecycle_and_events(
    db: Session,
) -> None:
    service = make_service(db)
    signal = service.create(
        make_request()
    )

    signal = service.transition(
        signal_id=signal.id,
        request=SignalTransitionRequest(
            status=(
                SignalStatus.ENTRY_REACHED
            ),
            price=Decimal("64150"),
            note="Entry range reached.",
        ),
    )

    assert signal.status == "ENTRY_REACHED"
    assert signal.entry_reached_at is not None

    signal = service.transition(
        signal_id=signal.id,
        request=SignalTransitionRequest(
            status=SignalStatus.TP1_REACHED,
            price=Decimal("65500"),
        ),
    )

    assert signal.status == "TP1_REACHED"

    events = service.events(signal.id)

    assert [
        event.to_status
        for event in events
    ] == [
        "ACTIVE",
        "ENTRY_REACHED",
        "TP1_REACHED",
    ]

    with pytest.raises(
        InvalidSignalTransitionError
    ):
        service.transition(
            signal_id=signal.id,
            request=(
                SignalTransitionRequest(
                    status=(
                        SignalStatus
                        .ENTRY_REACHED
                    )
                )
            ),
        )


def test_invalid_long_levels_are_rejected(
) -> None:
    with pytest.raises(ValidationError):
        make_request(
            stop_loss=Decimal("65000")
        )


def test_new_hour_allows_new_signal(
    db: Session,
) -> None:
    service = make_service(db)

    first = service.create(
        make_request()
    )

    second = service.create(
        make_request(
            generated_at=(
                first.generated_at
                + timedelta(hours=1)
            ),
            expires_at=(
                first.generated_at
                + timedelta(hours=25)
            ),
        )
    )

    assert first.id != second.id
    assert (
        first.fingerprint
        != second.fingerprint
    )
