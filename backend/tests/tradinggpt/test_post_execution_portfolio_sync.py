from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.tradinggpt.orders.execution_models import (
    OrderExecutionResult,
)
from app.tradinggpt.orders.journal_service import (
    JournaledOrderService,
)
from app.tradinggpt.orders.models import OrderIntent
from app.tradinggpt.orders.repository import (
    TradingOrderRepository,
)
from app.tradinggpt.orders.schemas import (
    JournalOrderExecuteRequest,
)
from app.tradinggpt.orders.validation_models import (
    OrderPreviewResult,
)
from app.tradinggpt.portfolio_sync.models import (
    AssetBalance,
    PortfolioSnapshot,
)


class FakeExecutionService:
    def preview(
        self,
        intent: OrderIntent,
    ) -> OrderPreviewResult:
        return OrderPreviewResult(
            exchange=intent.exchange,
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            valid=True,
            requested_quantity=intent.quantity,
            normalized_quantity=intent.quantity,
            requested_price=intent.reference_price,
            normalized_price=intent.reference_price,
            estimated_notional=(
                intent.quantity
                * float(intent.reference_price or 0)
            ),
            available_balance=None,
            balance_asset=None,
            errors=[],
            warnings=[],
        )

    def execute(
        self,
        intent: OrderIntent,
    ) -> OrderExecutionResult:
        return OrderExecutionResult(
            exchange=intent.exchange,
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            status="FILLED",
            client_order_id="client-sync",
            exchange_order_id="order-sync",
            requested_quantity=intent.quantity,
            filled_quantity=intent.quantity,
            average_price=intent.reference_price,
            simulated=True,
            message="Order filled.",
        )


class FakePortfolioSyncService:
    def __init__(
        self,
        *,
        fail: bool = False,
    ) -> None:
        self.fail = fail
        self.calls: list[str] = []

    def get_snapshot(
        self,
        *,
        source: str,
    ) -> PortfolioSnapshot:
        self.calls.append(source)

        if self.fail:
            raise RuntimeError(
                "Temporary portfolio sync failure."
            )

        return PortfolioSnapshot(
            source=source,
            balances=[
                AssetBalance(
                    asset="USDT",
                    free=9000.0,
                    locked=0.0,
                )
            ],
            open_orders=[],
            positions=[],
            total_wallet_balance=9000.0,
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


def build_request(
    *,
    dry_run: bool,
    key: str,
) -> JournalOrderExecuteRequest:
    return JournalOrderExecuteRequest(
        idempotency_key=key,
        dry_run=dry_run,
        exchange="PAPER",
        market_type="SPOT",
        symbol="BTCUSDT",
        side="BUY",
        order_type="MARKET",
        quantity=0.001,
        reference_price=60_000.0,
        leverage=1,
        reduce_only=False,
    )


def test_successful_execution_attaches_snapshot() -> None:
    with build_session() as session:
        portfolio = FakePortfolioSyncService()
        service = JournaledOrderService(
            repository=TradingOrderRepository(
                session
            ),
            execution_service=FakeExecutionService(),
            portfolio_sync_service=portfolio,
        )

        result = service.execute(
            build_request(
                dry_run=False,
                key="sync-success",
            )
        )

        sync = result[
            "execution_payload"
        ]["portfolio_sync"]

        assert sync["status"] == "SYNCED"
        assert sync["source"] == "PAPER"
        assert (
            sync["snapshot"]["total_wallet_balance"]
            == 9000.0
        )
        assert portfolio.calls == ["PAPER"]


def test_dry_run_does_not_sync_portfolio() -> None:
    with build_session() as session:
        portfolio = FakePortfolioSyncService()
        service = JournaledOrderService(
            repository=TradingOrderRepository(
                session
            ),
            execution_service=FakeExecutionService(),
            portfolio_sync_service=portfolio,
        )

        result = service.execute(
            build_request(
                dry_run=True,
                key="sync-dry-run",
            )
        )

        assert result["status"] == "DRY_RUN"
        assert portfolio.calls == []
        assert (
            "portfolio_sync"
            not in result["execution_payload"]
        )


def test_sync_failure_does_not_fail_filled_order() -> None:
    with build_session() as session:
        portfolio = FakePortfolioSyncService(
            fail=True
        )
        service = JournaledOrderService(
            repository=TradingOrderRepository(
                session
            ),
            execution_service=FakeExecutionService(),
            portfolio_sync_service=portfolio,
        )

        result = service.execute(
            build_request(
                dry_run=False,
                key="sync-failure",
            )
        )

        sync = result[
            "execution_payload"
        ]["portfolio_sync"]

        assert result["status"] == "FILLED"
        assert sync["status"] == "FAILED"
        assert (
            "Temporary portfolio sync failure"
            in sync["error"]
        )
