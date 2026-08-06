from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models.trading_order import TradingOrder
from app.tradinggpt.orders.repository import (
    TradingOrderRepository,
)


def build_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    return Session(engine)


def test_repository_creates_and_finds_order() -> None:
    with build_session() as session:
        repository = TradingOrderRepository(session)

        order = repository.create(
            idempotency_key="signal-123",
            exchange="BINANCE",
            market_type="SPOT",
            symbol="BTCUSDT",
            side="BUY",
            order_type="LIMIT",
            requested_quantity=0.001,
            requested_price=62000.0,
            dry_run=False,
            request_payload={
                "symbol": "BTCUSDT",
            },
        )

        session.commit()

        stored = repository.get_by_id(order.id)
        duplicate = repository.get_by_idempotency_key(
            "signal-123"
        )

        assert stored is not None
        assert duplicate is not None
        assert stored.id == duplicate.id
        assert stored.status == "PENDING"
        assert stored.symbol == "BTCUSDT"


def test_repository_applies_preview_and_execution() -> None:
    with build_session() as session:
        repository = TradingOrderRepository(session)

        order = repository.create(
            idempotency_key="signal-456",
            exchange="PAPER",
            market_type="SPOT",
            symbol="ETHUSDT",
            side="BUY",
            order_type="MARKET",
            requested_quantity=0.1,
            requested_price=3000.0,
            dry_run=True,
            request_payload={},
        )

        repository.apply_preview(
            order,
            valid=True,
            normalized_quantity=0.1,
            normalized_price=3000.0,
            preview_payload={
                "valid": True,
            },
        )

        assert order.status == "PREVIEWED"

        repository.apply_execution(
            order,
            status="FILLED",
            client_order_id="client-1",
            exchange_order_id="paper-1",
            filled_quantity=0.1,
            average_price=3000.0,
            simulated=True,
            execution_payload={
                "status": "FILLED",
            },
        )

        session.commit()

        assert order.status == "FILLED"
        assert float(order.filled_quantity) == 0.1
        assert float(order.average_price) == 3000.0
        assert order.simulated is True


def test_repository_lists_recent_with_filters() -> None:
    with build_session() as session:
        repository = TradingOrderRepository(session)

        repository.create(
            idempotency_key="first",
            exchange="PAPER",
            market_type="SPOT",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            requested_quantity=0.01,
            requested_price=60000.0,
            dry_run=True,
            request_payload={},
            status="FILLED",
        )
        repository.create(
            idempotency_key="second",
            exchange="BINANCE",
            market_type="SPOT",
            symbol="ETHUSDT",
            side="SELL",
            order_type="LIMIT",
            requested_quantity=0.2,
            requested_price=3000.0,
            dry_run=False,
            request_payload={},
            status="OPEN",
        )

        session.commit()

        results = repository.list_recent(
            exchange="BINANCE",
            status="OPEN",
        )

        assert len(results) == 1
        assert results[0].idempotency_key == "second"


def test_repository_isolates_orders_by_user(
) -> None:
    with build_session() as session:
        first_repository = (
            TradingOrderRepository(
                session,
                user_id=7,
                exchange_account_id=70,
            )
        )
        second_repository = (
            TradingOrderRepository(
                session,
                user_id=8,
                exchange_account_id=80,
            )
        )

        first = first_repository.create(
            idempotency_key="shared-key",
            exchange="BINANCE",
            market_type="SPOT",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            requested_quantity=0.001,
            requested_price=60_000.0,
            dry_run=False,
            request_payload={},
        )

        second = second_repository.create(
            idempotency_key="shared-key",
            exchange="BINANCE",
            market_type="SPOT",
            symbol="ETHUSDT",
            side="BUY",
            order_type="MARKET",
            requested_quantity=0.01,
            requested_price=3_000.0,
            dry_run=False,
            request_payload={},
        )

        session.commit()

        assert first.id != second.id
        assert first.user_id == 7
        assert first.exchange_account_id == 70
        assert second.user_id == 8
        assert second.exchange_account_id == 80

        assert (
            first_repository
            .get_by_id(second.id)
            is None
        )

        first_duplicate = (
            first_repository
            .get_by_idempotency_key(
                "shared-key"
            )
        )
        second_duplicate = (
            second_repository
            .get_by_idempotency_key(
                "shared-key"
            )
        )

        assert first_duplicate is not None
        assert second_duplicate is not None
        assert first_duplicate.id == first.id
        assert second_duplicate.id == second.id

        first_results = (
            first_repository.list_recent()
        )
        second_results = (
            second_repository.list_recent()
        )

        assert [
            item.id
            for item in first_results
        ] == [first.id]

        assert [
            item.id
            for item in second_results
        ] == [second.id]
