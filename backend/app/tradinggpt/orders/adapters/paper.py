from __future__ import annotations

from ..execution_models import OrderExecutionResult
from ..models import ExchangeName, OrderIntent


class PaperOrderAdapter:
    @property
    def exchange(self) -> ExchangeName:
        return "PAPER"

    def execute(
        self,
        *,
        intent: OrderIntent,
        client_order_id: str,
    ) -> OrderExecutionResult:
        if intent.exchange != self.exchange:
            raise ValueError(
                "PaperOrderAdapter only supports PAPER orders."
            )

        if intent.quantity <= 0:
            return self._rejected(
                intent=intent,
                client_order_id=client_order_id,
                message="Order quantity must be greater than zero.",
            )

        if intent.reference_price is None:
            return self._rejected(
                intent=intent,
                client_order_id=client_order_id,
                message="Reference price is required.",
            )

        exchange_order_id = f"paper-{client_order_id}"

        if intent.order_type == "LIMIT":
            return OrderExecutionResult(
                exchange="PAPER",
                symbol=intent.symbol,
                side=intent.side,
                order_type=intent.order_type,
                status="OPEN",
                client_order_id=client_order_id,
                exchange_order_id=exchange_order_id,
                requested_quantity=intent.quantity,
                filled_quantity=0.0,
                average_price=None,
                simulated=True,
                message="Paper limit order accepted.",
            )

        return OrderExecutionResult(
            exchange="PAPER",
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            status="FILLED",
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            requested_quantity=intent.quantity,
            filled_quantity=intent.quantity,
            average_price=intent.reference_price,
            simulated=True,
            message="Paper market order filled.",
        )

    @staticmethod
    def _rejected(
        *,
        intent: OrderIntent,
        client_order_id: str,
        message: str,
    ) -> OrderExecutionResult:
        return OrderExecutionResult(
            exchange="PAPER",
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            status="REJECTED",
            client_order_id=client_order_id,
            exchange_order_id=None,
            requested_quantity=intent.quantity,
            filled_quantity=0.0,
            average_price=None,
            simulated=True,
            message=message,
        )
