from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.tradinggpt.positions.repository import (
    TradingPositionRepository,
)
from app.tradinggpt.positions.schemas import (
    PositionCreateRequest,
)
from app.tradinggpt.positions.service import (
    PositionService,
)


def build_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def request() -> PositionCreateRequest:
    return PositionCreateRequest(
        exchange="PAPER",
        market_type="SPOT",
        symbol="BTCUSDT",
        side="LONG",
        quantity=1.0,
        entry_price=100.0,
        stop_loss=90.0,
        take_profit_1=110.0,
        take_profit_2=120.0,
    )


def test_service_creates_and_reads_position() -> None:
    with build_session() as session:
        service = PositionService(
            repository=TradingPositionRepository(
                session
            )
        )

        created = service.create(request())
        stored = service.get(created["id"])

        assert stored is not None
        assert stored["status"] == "OPEN"
        assert created["actions"] == [
            "POSITION_CREATED"
        ]


def test_service_updates_and_commits_tp1() -> None:
    with build_session() as session:
        service = PositionService(
            repository=TradingPositionRepository(
                session
            )
        )

        created = service.create(request())
        result = service.update_price(
            position_id=created["id"],
            current_price=110.0,
        )

        assert result is not None
        assert result["status"] == "PARTIALLY_CLOSED"
        assert result["remaining_quantity"] == 0.5
        assert result["realized_pnl"] == 5.0
        assert "TAKE_PROFIT_1" in result["actions"]


def test_service_closes_position() -> None:
    with build_session() as session:
        service = PositionService(
            repository=TradingPositionRepository(
                session
            )
        )

        created = service.create(request())
        result = service.close(
            position_id=created["id"],
            exit_price=105.0,
        )

        assert result is not None
        assert result["status"] == "CLOSED"
        assert result["realized_pnl"] == 5.0
        assert result["actions"] == [
            "MANUAL_CLOSE"
        ]


def test_position_levels_are_validated() -> None:
    try:
        PositionCreateRequest(
            exchange="PAPER",
            market_type="SPOT",
            symbol="BTCUSDT",
            side="LONG",
            quantity=1.0,
            entry_price=100.0,
            stop_loss=105.0,
            take_profit_1=110.0,
            take_profit_2=120.0,
        )
    except ValueError as exc:
        assert (
            "stop_loss must be below"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Invalid LONG stop loss was accepted."
        )
