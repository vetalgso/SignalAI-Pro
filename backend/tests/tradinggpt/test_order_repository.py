from __future__ import annotations

from datetime import datetime, timezone

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

def test_repository_isolates_orders_by_exchange_account(
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
                user_id=7,
                exchange_account_id=71,
            )
        )

        first = first_repository.create(
            idempotency_key="account-70",
            exchange="BINANCE",
            market_type="SPOT",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            requested_quantity=0.001,
            requested_price=60_000.0,
            dry_run=True,
            request_payload={},
        )

        second = second_repository.create(
            idempotency_key="account-71",
            exchange="BINANCE",
            market_type="SPOT",
            symbol="ETHUSDT",
            side="BUY",
            order_type="MARKET",
            requested_quantity=0.01,
            requested_price=3_000.0,
            dry_run=True,
            request_payload={},
        )

        session.commit()

        assert (
            first_repository.get_by_id(
                second.id
            )
            is None
        )

        assert (
            second_repository.get_by_id(
                first.id
            )
            is None
        )

        assert [
            item.id
            for item in (
                first_repository
                .list_recent()
            )
        ] == [first.id]

        assert [
            item.id
            for item in (
                second_repository
                .list_recent()
            )
        ] == [second.id]

        assert (
            first_repository
            .get_by_idempotency_key(
                "account-71"
            )
            is not None
        )



def create_risk_usage_order(
    repository: TradingOrderRepository,
    *,
    idempotency_key: str,
    status: str,
    estimated_notional: float,
    dry_run: bool = False,
) -> TradingOrder:
    order = repository.create(
        idempotency_key=idempotency_key,
        exchange="BINANCE",
        market_type="SPOT",
        symbol="BTCUSDT",
        side="BUY",
        order_type="LIMIT",
        requested_quantity=0.001,
        requested_price=60_000.0,
        dry_run=dry_run,
        request_payload={},
    )

    repository.apply_preview(
        order,
        valid=True,
        normalized_quantity=0.001,
        normalized_price=60_000.0,
        estimated_notional=(
            estimated_notional
        ),
        preview_payload={
            "valid": True,
            "estimated_notional": (
                estimated_notional
            ),
        },
    )

    repository.apply_execution(
        order,
        status=status,
        client_order_id=None,
        exchange_order_id=None,
        filled_quantity=(
            0.001
            if status == "FILLED"
            else 0.0
        ),
        average_price=(
            60_000.0
            if status == "FILLED"
            else None
        ),
        simulated=dry_run,
        execution_payload={
            "status": status,
        },
    )

    return order


def test_repository_calculates_account_risk_usage(
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
                user_id=7,
                exchange_account_id=71,
            )
        )

        create_risk_usage_order(
            first_repository,
            idempotency_key="filled-70",
            status="FILLED",
            estimated_notional=60.0,
        )
        create_risk_usage_order(
            first_repository,
            idempotency_key="open-70",
            status="OPEN",
            estimated_notional=40.0,
        )
        create_risk_usage_order(
            first_repository,
            idempotency_key="dry-run-70",
            status="DRY_RUN",
            estimated_notional=900.0,
            dry_run=True,
        )
        create_risk_usage_order(
            second_repository,
            idempotency_key="filled-71",
            status="FILLED",
            estimated_notional=500.0,
        )

        session.commit()

        since = datetime(
            2000,
            1,
            1,
            tzinfo=timezone.utc,
        )

        first_usage = (
            first_repository.get_risk_usage(
                since=since
            )
        )
        second_usage = (
            second_repository.get_risk_usage(
                since=since
            )
        )

        assert first_usage.daily_notional == 100.0
        assert first_usage.open_orders == 1

        assert second_usage.daily_notional == 500.0
        assert second_usage.open_orders == 0

def test_repository_lists_reconciliation_candidates(
) -> None:
    with build_session() as session:
        def create_order(
            *,
            key: str,
            account_id: int,
            exchange: str,
            status: str,
            dry_run: bool,
            exchange_order_id: str | None,
        ) -> object:
            repository = TradingOrderRepository(
                session,
                user_id=7,
                exchange_account_id=(
                    account_id
                ),
            )

            order = repository.create(
                idempotency_key=key,
                exchange=exchange,
                market_type="SPOT",
                symbol="BTCUSDT",
                side="BUY",
                order_type="LIMIT",
                requested_quantity=0.001,
                requested_price=50000.0,
                dry_run=dry_run,
                request_payload={},
            )

            repository.apply_execution(
                order,
                status=status,
                client_order_id=(
                    f"client-{key}"
                ),
                exchange_order_id=(
                    exchange_order_id
                ),
                filled_quantity=0.0,
                average_price=None,
                simulated=False,
                execution_payload={},
            )

            return order

        open_order = create_order(
            key="reconcile-open",
            account_id=42,
            exchange="BINANCE",
            status="OPEN",
            dry_run=False,
            exchange_order_id="remote-open",
        )
        partial_order = create_order(
            key="reconcile-partial",
            account_id=42,
            exchange="BINANCE",
            status="PARTIALLY_FILLED",
            dry_run=False,
            exchange_order_id="remote-partial",
        )

        create_order(
            key="ignore-dry-run",
            account_id=42,
            exchange="BINANCE",
            status="OPEN",
            dry_run=True,
            exchange_order_id="remote-dry",
        )
        create_order(
            key="ignore-paper",
            account_id=42,
            exchange="PAPER",
            status="OPEN",
            dry_run=False,
            exchange_order_id="remote-paper",
        )
        create_order(
            key="ignore-filled",
            account_id=42,
            exchange="BINANCE",
            status="FILLED",
            dry_run=False,
            exchange_order_id="remote-filled",
        )
        create_order(
            key="ignore-missing-remote-id",
            account_id=42,
            exchange="BINANCE",
            status="OPEN",
            dry_run=False,
            exchange_order_id=None,
        )

        session.commit()

        results = (
            TradingOrderRepository(session)
            .list_reconciliation_candidates(
                limit=10
            )
        )

        assert {
            order.id
            for order in results
        } == {
            open_order.id,
            partial_order.id,
        }
