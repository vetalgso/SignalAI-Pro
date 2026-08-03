from __future__ import annotations

from dataclasses import dataclass, replace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.tradinggpt.decision import (
    FinalTradeDecision,
)
from app.tradinggpt.orders import OrderIntent
from app.tradinggpt.orders.execution_models import (
    OrderExecutionResult,
)
from app.tradinggpt.orders.journal_service import (
    JournaledOrderService,
)
from app.tradinggpt.orders.repository import (
    TradingOrderRepository,
)
from app.tradinggpt.orders.validation_models import (
    OrderPreviewResult,
)
from app.tradinggpt.engine.execution_service import (
    AnalyzeAndExecuteService,
)


class FakeExecutionService:
    def __init__(self) -> None:
        self.execute_calls = 0

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
        self.execute_calls += 1

        return OrderExecutionResult(
            exchange=intent.exchange,
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            status="FILLED",
            client_order_id="pipeline-client",
            exchange_order_id="pipeline-order",
            requested_quantity=intent.quantity,
            filled_quantity=intent.quantity,
            average_price=intent.reference_price,
            simulated=True,
            message="Pipeline order filled.",
        )


@dataclass
class FakeAnalysis:
    decision: FinalTradeDecision | None
    order_intent: OrderIntent | None

    def to_dict(self) -> dict[str, object]:
        return {
            "scoring": {},
            "market_regime": {},
            "portfolio": {},
            "conviction": {},
            "explanation": {},
            "execution_plan": None,
            "risk_decision": None,
            "decision": (
                self.decision.to_dict()
                if self.decision is not None
                else None
            ),
            "order_intent": (
                self.order_intent.to_dict()
                if self.order_intent is not None
                else None
            ),
        }


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


def executable_decision() -> FinalTradeDecision:
    return FinalTradeDecision(
        status="EXECUTE",
        symbol="BTCUSDT",
        side="BUY",
        recommendation="BUY",
        approved_quantity=0.001,
        approved_value=60.0,
        approved_risk=1.0,
        conviction_score=90.0,
        execution_ready=True,
        risk_allowed=True,
        summary="Trade approved.",
    )


def order_intent() -> OrderIntent:
    return OrderIntent(
        exchange="PAPER",
        market_type="SPOT",
        symbol="BTCUSDT",
        side="BUY",
        order_type="MARKET",
        quantity=0.001,
        reference_price=60_000.0,
        stop_loss=59_000.0,
        take_profit_1=61_500.0,
        take_profit_2=63_000.0,
        leverage=1,
        reduce_only=False,
    )


def test_no_trade_is_skipped() -> None:
    with build_session() as session:
        fake_execution = FakeExecutionService()
        service = AnalyzeAndExecuteService(
            journal_service=JournaledOrderService(
                repository=TradingOrderRepository(
                    session
                ),
                execution_service=fake_execution,
            )
        )

        decision = executable_decision()
        blocked = replace(
            decision,
            status="NO_TRADE",
            execution_ready=False,
        )

        result = service.execute(
            analysis=FakeAnalysis(
                decision=blocked,
                order_intent=None,
            ),
            dry_run=True,
        )

        assert result["action"] == "SKIPPED"
        assert result["journal"] is None
        assert fake_execution.execute_calls == 0


def test_executable_decision_creates_dry_run() -> None:
    with build_session() as session:
        fake_execution = FakeExecutionService()
        service = AnalyzeAndExecuteService(
            journal_service=JournaledOrderService(
                repository=TradingOrderRepository(
                    session
                ),
                execution_service=fake_execution,
            )
        )

        result = service.execute(
            analysis=FakeAnalysis(
                decision=executable_decision(),
                order_intent=order_intent(),
            ),
            dry_run=True,
        )

        assert result["action"] == "DRY_RUN"
        assert result["journal"]["status"] == "DRY_RUN"
        assert fake_execution.execute_calls == 0


def test_generated_key_prevents_duplicate_execution() -> None:
    with build_session() as session:
        fake_execution = FakeExecutionService()
        service = AnalyzeAndExecuteService(
            journal_service=JournaledOrderService(
                repository=TradingOrderRepository(
                    session
                ),
                execution_service=fake_execution,
            )
        )
        analysis = FakeAnalysis(
            decision=executable_decision(),
            order_intent=order_intent(),
        )

        first = service.execute(
            analysis=analysis,
            dry_run=False,
        )
        second = service.execute(
            analysis=analysis,
            dry_run=False,
        )

        assert first["action"] == "EXECUTED"
        assert second["action"] == "REPLAYED"
        assert (
            first["journal"]["journal_id"]
            == second["journal"]["journal_id"]
        )
        assert fake_execution.execute_calls == 1
