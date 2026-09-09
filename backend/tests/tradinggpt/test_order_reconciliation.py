from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.tradinggpt.orders.execution_models import (
    OrderExecutionResult,
)
from app.tradinggpt.orders.journal_service import (
    JournaledOrderService,
    OrderReconciliationUnavailableError,
)
from app.tradinggpt.orders.repository import (
    TradingOrderRepository,
)


class UnusedExecutionService:
    pass


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


def create_open_order(
    repository: TradingOrderRepository,
    *,
    idempotency_key: str,
    exchange_order_id: str,
) -> int:
    order = repository.create(
        idempotency_key=idempotency_key,
        exchange="BINANCE",
        market_type="SPOT",
        symbol="BTCUSDT",
        side="BUY",
        order_type="LIMIT",
        requested_quantity=0.002,
        requested_price=50_000.0,
        dry_run=False,
        request_payload={},
    )

    repository.apply_preview(
        order,
        valid=True,
        normalized_quantity=0.002,
        normalized_price=50_000.0,
        estimated_notional=100.0,
        preview_payload={
            "valid": True,
        },
    )

    repository.apply_execution(
        order,
        status="OPEN",
        client_order_id="client-1",
        exchange_order_id=(
            exchange_order_id
        ),
        filled_quantity=0.0,
        average_price=None,
        simulated=True,
        execution_payload={
            "initial": True,
        },
    )

    repository._session.commit()

    return order.id


def remote_result(
    *,
    status: str,
    exchange_order_id: str | None = (
        "exchange-1"
    ),
    filled_quantity: float = 0.002,
    average_price: float | None = (
        50_000.0
    ),
) -> OrderExecutionResult:
    return OrderExecutionResult(
        exchange="BINANCE",
        symbol="BTCUSDT",
        side="BUY",
        order_type="LIMIT",
        status=status,
        client_order_id="client-1",
        exchange_order_id=(
            exchange_order_id
        ),
        requested_quantity=0.002,
        filled_quantity=filled_quantity,
        average_price=average_price,
        simulated=True,
        message=(
            f"Remote status: {status}."
        ),
    )


def test_reconciliation_updates_scoped_journal(
) -> None:
    with build_session() as session:
        repository = TradingOrderRepository(
            session,
            user_id=7,
            exchange_account_id=42,
        )
        journal_id = create_open_order(
            repository,
            idempotency_key="reconcile-filled",
            exchange_order_id="exchange-1",
        )

        service = JournaledOrderService(
            repository=repository,
            execution_service=(
                UnusedExecutionService()
            ),
        )

        result = (
            service.reconcile_remote_result(
                remote_result(
                    status="FILLED"
                )
            )
        )

        assert result is not None
        assert result["journal_id"] == journal_id
        assert result["status"] == "FILLED"
        assert result["filled_quantity"] == 0.002
        assert result["average_price"] == 50_000.0

        stored = repository.get_by_id(
            journal_id
        )

        assert stored is not None
        assert stored.status == "FILLED"
        assert (
            stored.execution_payload[
                "initial"
            ]
            is True
        )
        assert (
            stored.execution_payload[
                "last_reconciliation"
            ]["result"]["status"]
            == "FILLED"
        )


def test_reconciliation_respects_account_scope(
) -> None:
    with build_session() as session:
        owner = TradingOrderRepository(
            session,
            user_id=7,
            exchange_account_id=42,
        )
        journal_id = create_open_order(
            owner,
            idempotency_key="reconcile-scope",
            exchange_order_id="exchange-1",
        )

        foreign = TradingOrderRepository(
            session,
            user_id=7,
            exchange_account_id=43,
        )
        service = JournaledOrderService(
            repository=foreign,
            execution_service=(
                UnusedExecutionService()
            ),
        )

        result = (
            service.reconcile_remote_result(
                remote_result(
                    status="FILLED"
                )
            )
        )

        assert result is None

        stored = owner.get_by_id(journal_id)

        assert stored is not None
        assert stored.status == "OPEN"


def test_reconciliation_fails_closed(
) -> None:
    with build_session() as session:
        repository = TradingOrderRepository(
            session,
            user_id=7,
            exchange_account_id=42,
        )
        journal_id = create_open_order(
            repository,
            idempotency_key="reconcile-failed",
            exchange_order_id="exchange-1",
        )

        service = JournaledOrderService(
            repository=repository,
            execution_service=(
                UnusedExecutionService()
            ),
        )

        with pytest.raises(
            OrderReconciliationUnavailableError,
            match="could not be reconciled",
        ):
            service.reconcile_remote_result(
                remote_result(
                    status="FAILED",
                    filled_quantity=0.0,
                    average_price=None,
                )
            )

        stored = repository.get_by_id(
            journal_id
        )

        assert stored is not None
        assert stored.status == "OPEN"


def test_partial_fill_remains_in_daily_risk_after_cancel(
) -> None:
    with build_session() as session:
        repository = TradingOrderRepository(
            session,
            user_id=7,
            exchange_account_id=42,
        )
        create_open_order(
            repository,
            idempotency_key=(
                "reconcile-partial-cancel"
            ),
            exchange_order_id="exchange-1",
        )

        service = JournaledOrderService(
            repository=repository,
            execution_service=(
                UnusedExecutionService()
            ),
        )

        result = (
            service.reconcile_remote_result(
                remote_result(
                    status="CANCELED",
                    filled_quantity=0.001,
                    average_price=50_000.0,
                )
            )
        )

        assert result is not None
        assert result["status"] == "CANCELED"

        usage = (
            repository
            .get_today_risk_usage()
        )

        assert usage.daily_notional == 100.0
        assert usage.open_orders == 0
