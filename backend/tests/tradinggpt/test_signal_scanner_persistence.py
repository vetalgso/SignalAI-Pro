from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from app.models.trading_signal import (
    TradingSignal,
    TradingSignalEvent,
)
from app.tradinggpt.signals.generator import (
    TradingSignalGenerator,
)
from app.tradinggpt.signals.repository import (
    TradingSignalRepository,
)
from app.tradinggpt.signals.service import (
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

    TradingSignal.__table__.create(
        engine
    )
    TradingSignalEvent.__table__.create(
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


def generator(
    db: Session,
) -> TradingSignalGenerator:
    return TradingSignalGenerator(
        TradingSignalService(
            TradingSignalRepository(db)
        )
    )


def opportunity(
    *,
    symbol: str = "BTCUSDT",
    action: str = "LONG",
    recommendation: str = "LONG",
    confidence: int = 78,
    entry: str = "64000",
    stop_loss: str = "62500",
    take_profit: str = "67000",
) -> dict[str, object]:
    return {
        "asset": symbol.removesuffix(
            "USDT"
        ),
        "symbol": symbol,
        "score": 72.0,
        "opportunity_score": 75.0,
        "consensus_score": 80.0,
        "timeframe_consensus_score": 75.0,
        "ranking_score": 77.0,
        "confidence": confidence,
        "risk": "medium",
        "recommendation": recommendation,
        "trade_direction": action,
        "signal_action": action,
        "forecast_direction": "UP",
        "timeframe_directions": {
            "1H": action,
            "4H": action,
        },
        "trend_direction": action,
        "trade_style": (
            "TREND_FOLLOWING"
        ),
        "reasons": [
            "Technical trend confirmed.",
            "Timeframes agree.",
        ],
        "quality_penalty": 0,
        "warnings": [],
        "market_price": entry,
        "signal_strategy": (
            "technical_confluence_v1"
        ),
        "signal_levels": {
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_reward_ratio": 2.0,
        },
    }


def scan(
    *items: dict[str, object],
) -> dict[str, object]:
    return {
        "scanned_assets": len(items),
        "successful_assets": len(items),
        "failed_assets": 0,
        "opportunities": list(items),
        "watchlist": [],
        "avoid": [],
        "ranking": list(items),
        "errors": [],
    }


def test_persists_long_scanner_signal(
    db: Session,
) -> None:
    result = generator(db).persist_scan(
        scan_result=scan(
            opportunity()
        ),
        min_confidence=Decimal("60"),
    )

    assert result["created_count"] == 1
    assert result["duplicate_count"] == 0
    assert result["skipped_count"] == 0

    signal = result["created"][0]

    assert signal.symbol == "BTCUSDT"
    assert signal.side == "LONG"
    assert signal.source == "MARKET_SCANNER"
    assert signal.entry_min == Decimal(
        "64000"
    )
    assert signal.entry_max == Decimal(
        "64000"
    )
    assert signal.stop_loss == Decimal(
        "62500"
    )
    assert signal.take_profit_1 == Decimal(
        "65500"
    )
    assert signal.take_profit_2 == Decimal(
        "67000"
    )
    assert signal.take_profit_3 == Decimal(
        "68500"
    )


def test_persists_short_scanner_signal(
    db: Session,
) -> None:
    result = generator(db).persist_scan(
        scan_result=scan(
            opportunity(
                symbol="ETHUSDT",
                action="SHORT",
                recommendation="SHORT",
                entry="3400",
                stop_loss="3500",
                take_profit="3200",
            )
        ),
        min_confidence=Decimal("60"),
    )

    signal = result["created"][0]

    assert signal.side == "SHORT"
    assert signal.take_profit_1 == Decimal(
        "3300"
    )
    assert signal.take_profit_2 == Decimal(
        "3200"
    )
    assert signal.take_profit_3 == Decimal(
        "3100"
    )


def test_duplicate_scan_is_counted(
    db: Session,
) -> None:
    service = generator(db)
    scan_result = scan(
        opportunity()
    )

    first = service.persist_scan(
        scan_result=scan_result,
        min_confidence=Decimal("60"),
    )
    second = service.persist_scan(
        scan_result=scan_result,
        min_confidence=Decimal("60"),
    )

    assert first["created_count"] == 1
    assert second["created_count"] == 0
    assert second["duplicate_count"] == 1
    assert (
        second["duplicates"][0][
            "existing_signal_id"
        ]
        == first["created"][0].id
    )


def test_skips_unsafe_opportunities(
    db: Session,
) -> None:
    low_confidence = opportunity(
        symbol="ADAUSDT",
        confidence=40,
    )

    direction_conflict = opportunity(
        symbol="SOLUSDT",
    )
    direction_conflict[
        "trade_direction"
    ] = "SHORT"

    missing_levels = opportunity(
        symbol="XRPUSDT",
    )
    missing_levels[
        "signal_levels"
    ] = None

    result = generator(db).persist_scan(
        scan_result=scan(
            low_confidence,
            direction_conflict,
            missing_levels,
        ),
        min_confidence=Decimal("60"),
    )

    assert result["created_count"] == 0
    assert result["skipped_count"] == 3

    assert {
        item["reason"]
        for item in result["skipped"]
    } == {
        "LOW_CONFIDENCE",
        "DIRECTION_CONFLICT",
        "LEVELS_UNAVAILABLE",
    }
