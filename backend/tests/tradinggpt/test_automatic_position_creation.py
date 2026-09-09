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
from app.tradinggpt.positions.repository import (
    TradingPositionRepository,
)


class FakeExecutionService:
    def __init__(
        self,
        *,
        status: str = "FILLED",
        side: str = "BUY",
    ) -> None:
        self.status = status
        self.side = side
        self.calls = 0

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
        self.calls += 1

        return OrderExecutionResult(
            exchange=intent.exchange,
            symbol=intent.symbol,
            side=self.side,
            order_type=intent.order_type,
            status=self.status,
            client_order_id="auto-position-client",
            exchange_order_id="auto-position-order",
            requested_quantity=intent.quantity,
            filled_quantity=(
                intent.quantity
                if self.status == "FILLED"
                else 0.0
            ),
            average_price=(
                100.0
                if self.status == "FILLED"
                else None
            ),
            simulated=True,
            message=f"Order status: {self.status}.",
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
    key: str,
    side: str = "BUY",
    dry_run: bool = False,
    reduce_only: bool = False,
) -> JournalOrderExecuteRequest:
    return JournalOrderExecuteRequest(
        idempotency_key=key,
        dry_run=dry_run,
        exchange="PAPER",
        market_type="SPOT",
        symbol="BTCUSDT",
        side=side,
        order_type="MARKET",
        quantity=1.0,
        reference_price=100.0,
        stop_loss=90.0 if side == "BUY" else 110.0,
        take_profit_1=(
            110.0 if side == "BUY" else 90.0
        ),
        take_profit_2=(
            120.0 if side == "BUY" else 80.0
        ),
        leverage=1,
        reduce_only=reduce_only,
    )


def build_service(
    session: Session,
    execution: FakeExecutionService,
) -> JournaledOrderService:
    return JournaledOrderService(
        repository=TradingOrderRepository(session),
        execution_service=execution,
        position_repository=(
            TradingPositionRepository(session)
        ),
    )


def test_filled_buy_creates_long_position() -> None:
    with build_session() as session:
        service = build_service(
            session,
            FakeExecutionService(),
        )

        result = service.execute(
            build_request(key="filled-buy")
        )

        position = (
            TradingPositionRepository(session)
            .get_by_journal_order_id(
                result["journal_id"]
            )
        )

        assert position is not None
        assert position.side == "LONG"
        assert float(position.initial_quantity) == 1.0
        assert float(position.entry_price) == 100.0
        assert float(position.stop_loss) == 90.0
        assert (
            result["execution_payload"]
            ["managed_position"]["status"]
            == "CREATED"
        )


def test_filled_sell_creates_short_position() -> None:
    with build_session() as session:
        execution = FakeExecutionService(
            side="SELL"
        )
        service = build_service(
            session,
            execution,
        )

        result = service.execute(
            build_request(
                key="filled-sell",
                side="SELL",
            )
        )

        position = (
            TradingPositionRepository(session)
            .get_by_journal_order_id(
                result["journal_id"]
            )
        )

        assert position is not None
        assert position.side == "SHORT"
        assert float(position.stop_loss) == 110.0


def test_dry_run_does_not_create_position() -> None:
    with build_session() as session:
        service = build_service(
            session,
            FakeExecutionService(),
        )

        result = service.execute(
            build_request(
                key="dry-run",
                dry_run=True,
            )
        )

        positions = (
            TradingPositionRepository(session)
            .list_positions()
        )

        assert result["status"] == "DRY_RUN"
        assert positions == []


def test_failed_order_does_not_create_position() -> None:
    with build_session() as session:
        service = build_service(
            session,
            FakeExecutionService(
                status="FAILED"
            ),
        )

        result = service.execute(
            build_request(key="failed-order")
        )

        positions = (
            TradingPositionRepository(session)
            .list_positions()
        )

        assert result["status"] == "FAILED"
        assert positions == []
        assert (
            result["execution_payload"]
            ["managed_position"]["status"]
            == "SKIPPED"
        )


def test_replay_does_not_duplicate_position() -> None:
    with build_session() as session:
        execution = FakeExecutionService()
        service = build_service(
            session,
            execution,
        )
        request = build_request(
            key="position-replay"
        )

        first = service.execute(request)
        second = service.execute(request)

        positions = (
            TradingPositionRepository(session)
            .list_positions()
        )

        assert first["journal_id"] == second[
            "journal_id"
        ]
        assert second["replayed"] is True
        assert len(positions) == 1
        assert execution.calls == 1
