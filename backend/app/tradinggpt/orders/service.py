from __future__ import annotations

from app.tradinggpt.decision import FinalTradeDecision
from app.tradinggpt.execution import ExecutionPlan

from .models import (
    OrderIntent,
    OrderRoutingContext,
)


class OrderIntentBuilder:
    """Converts an approved decision into an exchange-neutral order."""

    @classmethod
    def build(
        cls,
        *,
        decision: FinalTradeDecision,
        execution_plan: ExecutionPlan | None,
        routing: OrderRoutingContext | None = None,
    ) -> OrderIntent | None:
        if decision.status not in {
            "EXECUTE",
            "EXECUTE_REDUCED",
        }:
            return None

        if execution_plan is None:
            return None

        if execution_plan.status != "READY":
            return None

        if decision.approved_quantity <= 0:
            return None

        routing = routing or OrderRoutingContext()

        cls._validate_routing(routing)

        return OrderIntent(
            exchange=routing.exchange,
            market_type=routing.market_type,
            symbol=execution_plan.symbol,
            side=cls._resolve_side(execution_plan.side),
            order_type=routing.order_type,
            quantity=decision.approved_quantity,
            reference_price=execution_plan.entry_price,
            stop_loss=execution_plan.stop_loss,
            take_profit_1=execution_plan.take_profit_1,
            take_profit_2=execution_plan.take_profit_2,
            leverage=routing.leverage,
            reduce_only=False,
        )

    @staticmethod
    def _resolve_side(side: str) -> str:
        if side == "LONG":
            return "BUY"

        raise ValueError(
            f"Unsupported execution side: {side}"
        )

    @staticmethod
    def _validate_routing(
        routing: OrderRoutingContext,
    ) -> None:
        if routing.leverage < 1:
            raise ValueError(
                "Leverage must be greater than or equal to 1."
            )

        if (
            routing.market_type == "SPOT"
            and routing.leverage != 1
        ):
            raise ValueError(
                "Spot orders must use leverage=1."
            )
