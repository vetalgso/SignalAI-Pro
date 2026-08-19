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
from app.tradinggpt.orders.repository import (
    TradingOrderRepository,
)
from app.tradinggpt.orders.risk import (
    OrderRiskPolicy,
)
from app.tradinggpt.orders.schemas import (
    JournalOrderExecuteRequest,
)
from app.tradinggpt.orders.validation_models import (
    OrderPreviewResult,
)


class FakeExecutionService:
    def __init__(self) -> None:
        self.execute_calls = 0
        self.open_order_calls = 0
        self.open_orders: list[
            object
        ] = []

    def list_open_orders(
        self,
        *,
        exchange: str,
        symbol: str | None = None,
    ) -> list[object]:
        self.open_order_calls += 1

        return self.open_orders

    def preview(
        self,
        intent: object,
    ) -> OrderPreviewResult:
        return OrderPreviewResult(
            exchange="PAPER",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            valid=True,
            requested_quantity=0.01,
            normalized_quantity=0.01,
            requested_price=60_000.0,
            normalized_price=60_000.0,
            estimated_notional=600.0,
            available_balance=None,
            balance_asset=None,
            errors=[],
            warnings=[],
        )

    def execute(
        self,
        intent: object,
    ) -> OrderExecutionResult:
        self.execute_calls += 1

        return OrderExecutionResult(
            exchange="PAPER",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            status="FILLED",
            client_order_id="client-1",
            exchange_order_id="paper-1",
            requested_quantity=0.01,
            filled_quantity=0.01,
            average_price=60_000.0,
            simulated=True,
            message="Paper market order filled.",
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
    idempotency_key: str,
    dry_run: bool = False,
    reduce_only: bool = False,
) -> JournalOrderExecuteRequest:
    return JournalOrderExecuteRequest(
        idempotency_key=idempotency_key,
        dry_run=dry_run,
        exchange="PAPER",
        market_type="SPOT",
        symbol="BTCUSDT",
        side="BUY",
        order_type="MARKET",
        quantity=0.01,
        reference_price=60_000.0,
        leverage=1,
        reduce_only=reduce_only,
    )


def test_journal_executes_and_persists_order() -> None:
    with build_session() as session:
        execution = FakeExecutionService()
        service = JournaledOrderService(
            repository=TradingOrderRepository(
                session
            ),
            execution_service=execution,
        )

        result = service.execute(
            build_request(
                idempotency_key="signal-1"
            )
        )

        assert result["status"] == "FILLED"
        assert result["journal_id"] == 1
        assert result["replayed"] is False
        assert execution.execute_calls == 1


def test_idempotency_prevents_duplicate_execution() -> None:
    with build_session() as session:
        execution = FakeExecutionService()
        service = JournaledOrderService(
            repository=TradingOrderRepository(
                session
            ),
            execution_service=execution,
        )

        first = service.execute(
            build_request(
                idempotency_key="signal-2"
            )
        )
        second = service.execute(
            build_request(
                idempotency_key="signal-2"
            )
        )

        assert first["journal_id"] == second[
            "journal_id"
        ]
        assert second["replayed"] is True
        assert execution.execute_calls == 1


def test_dry_run_does_not_execute_order() -> None:
    with build_session() as session:
        execution = FakeExecutionService()
        service = JournaledOrderService(
            repository=TradingOrderRepository(
                session
            ),
            execution_service=execution,
        )

        result = service.execute(
            build_request(
                idempotency_key="signal-3",
                dry_run=True,
            )
        )

        assert result["status"] == "DRY_RUN"
        assert result["dry_run"] is True
        assert execution.execute_calls == 0

def test_journal_persists_user_and_account_scope(
) -> None:
    with build_session() as session:
        repository = TradingOrderRepository(
            session,
            user_id=7,
            exchange_account_id=42,
        )

        service = JournaledOrderService(
            repository=repository,
            execution_service=(
                FakeExecutionService()
            ),
        )

        result = service.execute(
            build_request(
                idempotency_key=(
                    "scoped-journal"
                ),
                dry_run=True,
            )
        )

        stored = repository.get_by_id(
            int(result["journal_id"])
        )

        assert stored is not None
        assert stored.user_id == 7
        assert (
            stored.exchange_account_id
            == 42
        )

        foreign_repository = (
            TradingOrderRepository(
                session,
                user_id=8,
                exchange_account_id=42,
            )
        )

        assert (
            foreign_repository.get_by_id(
                stored.id
            )
            is None
        )

        assert (
            foreign_repository
            .get_by_idempotency_key(
                "scoped-journal"
            )
            is None
        )

def test_risk_policy_blocks_execution_before_adapter(
) -> None:
    with build_session() as session:
        execution = FakeExecutionService()

        service = JournaledOrderService(
            repository=TradingOrderRepository(
                session
            ),
            execution_service=execution,
            risk_policy=(
                OrderRiskPolicy.configured(
                    execution_enabled=True,
                    max_order_notional=100.0,
                    allowed_symbols="BTCUSDT",
                )
            ),
        )

        result = service.execute(
            build_request(
                idempotency_key=(
                    "risk-blocked-order"
                )
            )
        )

        assert (
            result["status"]
            == "VALIDATION_FAILED"
        )
        assert execution.execute_calls == 0
        assert "exceeds" in str(
            result["error_message"]
        )

        preview_payload = result[
            "preview_payload"
        ]

        assert isinstance(
            preview_payload,
            dict,
        )
        assert (
            preview_payload["valid"]
            is False
        )



def test_journal_blocks_projected_daily_notional(
) -> None:
    with build_session() as session:
        execution = FakeExecutionService()
        repository = TradingOrderRepository(
            session,
            user_id=7,
            exchange_account_id=42,
        )

        repository.lock_risk_scope = (
            lambda: None
        )

        service = JournaledOrderService(
            repository=repository,
            execution_service=execution,
            risk_policy=(
                OrderRiskPolicy.configured(
                    execution_enabled=True,
                    max_order_notional=700.0,
                    max_daily_notional=1000.0,
                    max_open_orders=5,
                    allowed_symbols="BTCUSDT",
                )
            ),
        )

        first = service.execute(
            build_request(
                idempotency_key=(
                    "daily-risk-first"
                )
            )
        )
        second = service.execute(
            build_request(
                idempotency_key=(
                    "daily-risk-second"
                )
            )
        )

        assert first["status"] == "FILLED"
        assert (
            second["status"]
            == "VALIDATION_FAILED"
        )
        assert "Projected daily notional" in str(
            second["error_message"]
        )
        assert execution.execute_calls == 1

        usage = repository.get_today_risk_usage()

        assert usage.daily_notional == 600.0
        assert usage.open_orders == 0



def test_journal_uses_remote_open_order_count(
) -> None:
    with build_session() as session:
        execution = FakeExecutionService()
        execution.open_orders = [
            object(),
        ]

        repository = TradingOrderRepository(
            session,
            user_id=7,
            exchange_account_id=42,
        )
        repository.lock_risk_scope = (
            lambda: None
        )

        service = JournaledOrderService(
            repository=repository,
            execution_service=execution,
            risk_policy=(
                OrderRiskPolicy.configured(
                    execution_enabled=True,
                    max_order_notional=700.0,
                    max_daily_notional=1000.0,
                    max_open_orders=1,
                    allowed_symbols="BTCUSDT",
                )
            ),
        )

        result = service.execute(
            build_request(
                idempotency_key=(
                    "remote-open-limit"
                )
            )
        )

        assert (
            result["status"]
            == "VALIDATION_FAILED"
        )
        assert "Open order count 1" in str(
            result["error_message"]
        )
        assert execution.open_order_calls == 1
        assert execution.execute_calls == 0


def test_reduce_only_skips_remote_usage_limit(
) -> None:
    with build_session() as session:
        execution = FakeExecutionService()
        execution.open_orders = [
            object(),
        ]

        repository = TradingOrderRepository(
            session,
            user_id=7,
            exchange_account_id=42,
        )

        service = JournaledOrderService(
            repository=repository,
            execution_service=execution,
            risk_policy=(
                OrderRiskPolicy.configured(
                    execution_enabled=True,
                    max_order_notional=700.0,
                    max_daily_notional=500.0,
                    max_open_orders=1,
                    allowed_symbols="BTCUSDT",
                )
            ),
        )

        result = service.execute(
            build_request(
                idempotency_key=(
                    "reduce-only-risk-exit"
                ),
                reduce_only=True,
            )
        )

        assert result["status"] == "FILLED"
        assert execution.open_order_calls == 0
        assert execution.execute_calls == 1
