from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.tradinggpt.positions.manager import (
    PositionManager,
)
from app.tradinggpt.positions.repository import (
    TradingPositionRepository,
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


def create_long(
    repository: TradingPositionRepository,
):
    return repository.create(
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


def test_repository_creates_position() -> None:
    with build_session() as session:
        repository = TradingPositionRepository(
            session
        )
        position = create_long(repository)
        session.commit()

        stored = repository.get(position.id)

        assert stored is not None
        assert stored.status == "OPEN"
        assert float(stored.remaining_quantity) == 1.0


def test_price_update_calculates_unrealized_pnl() -> None:
    with build_session() as session:
        repository = TradingPositionRepository(
            session
        )
        position = create_long(repository)
        manager = PositionManager(
            repository=repository
        )

        result = manager.update_price(
            position=position,
            current_price=105.0,
        )

        assert result["status"] == "OPEN"
        assert result["unrealized_pnl"] == 5.0
        assert result["actions"] == ["PRICE_UPDATED"]


def test_tp1_partially_closes_and_moves_stop() -> None:
    with build_session() as session:
        repository = TradingPositionRepository(
            session
        )
        position = create_long(repository)
        manager = PositionManager(
            repository=repository
        )

        result = manager.update_price(
            position=position,
            current_price=110.0,
        )

        assert result["status"] == "PARTIALLY_CLOSED"
        assert result["remaining_quantity"] == 0.5
        assert result["closed_quantity"] == 0.5
        assert result["realized_pnl"] == 5.0
        assert result["stop_loss"] == 100.0
        assert result["break_even_activated"] is True


def test_tp2_closes_remaining_position() -> None:
    with build_session() as session:
        repository = TradingPositionRepository(
            session
        )
        position = create_long(repository)
        manager = PositionManager(
            repository=repository
        )

        manager.update_price(
            position=position,
            current_price=110.0,
        )
        result = manager.update_price(
            position=position,
            current_price=120.0,
        )

        assert result["status"] == "CLOSED"
        assert result["remaining_quantity"] == 0.0
        assert result["closed_quantity"] == 1.0
        assert result["realized_pnl"] == 15.0
        assert result["tp2_triggered"] is True


def test_stop_loss_closes_long_position() -> None:
    with build_session() as session:
        repository = TradingPositionRepository(
            session
        )
        position = create_long(repository)
        manager = PositionManager(
            repository=repository
        )

        result = manager.update_price(
            position=position,
            current_price=90.0,
        )

        assert result["status"] == "CLOSED"
        assert result["realized_pnl"] == -10.0
        assert result["stop_loss_triggered"] is True
        assert (
            result["metadata_payload"][
                "close_reason"
            ]
            == "STOP_LOSS"
        )


def test_short_position_uses_inverse_pnl() -> None:
    with build_session() as session:
        repository = TradingPositionRepository(
            session
        )
        position = repository.create(
            exchange="PAPER",
            market_type="FUTURES",
            symbol="BTCUSDT",
            side="SHORT",
            quantity=1.0,
            entry_price=100.0,
            stop_loss=110.0,
            take_profit_1=90.0,
            take_profit_2=80.0,
        )
        manager = PositionManager(
            repository=repository
        )

        result = manager.update_price(
            position=position,
            current_price=90.0,
        )

        assert result["realized_pnl"] == 5.0
        assert result["unrealized_pnl"] == 5.0
        assert result["remaining_quantity"] == 0.5
