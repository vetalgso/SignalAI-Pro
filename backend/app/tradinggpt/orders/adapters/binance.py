from __future__ import annotations

from typing import Any, Protocol

from ..execution_models import OrderExecutionResult
from ..models import ExchangeName, OrderIntent


class BinanceClientProtocol(Protocol):
    def create_order(
        self,
        **params: Any,
    ) -> dict[str, Any]:
        """Submit a Binance spot order."""


class BinanceOrderAdapter:
    """
    Binance Spot execution adapter.

    The adapter is dependency-injected and is not registered in the
    default execution service. This prevents accidental real execution.

    For testnet usage, initialize python-binance Client with testnet=True
    and pass it to this adapter.
    """

    def __init__(
        self,
        *,
        client: BinanceClientProtocol,
        testnet: bool = True,
    ) -> None:
        self._client = client
        self._testnet = testnet

    @property
    def exchange(self) -> ExchangeName:
        return "BINANCE"

    def execute(
        self,
        *,
        intent: OrderIntent,
        client_order_id: str,
    ) -> OrderExecutionResult:
        if intent.exchange != self.exchange:
            raise ValueError(
                "BinanceOrderAdapter only supports BINANCE orders."
            )

        if intent.market_type != "SPOT":
            return self._failed(
                intent=intent,
                client_order_id=client_order_id,
                message=(
                    "Binance futures execution is not supported "
                    "by this adapter."
                ),
            )

        try:
            params = self._build_order_params(
                intent=intent,
                client_order_id=client_order_id,
            )
            response = self._client.create_order(**params)
        except Exception as exc:
            return self._failed(
                intent=intent,
                client_order_id=client_order_id,
                message=f"Binance order failed: {exc}",
            )

        return self._map_response(
            intent=intent,
            client_order_id=client_order_id,
            response=response,
        )

    @staticmethod
    def _build_order_params(
        *,
        intent: OrderIntent,
        client_order_id: str,
    ) -> dict[str, object]:
        params: dict[str, object] = {
            "symbol": intent.symbol,
            "side": intent.side,
            "type": intent.order_type,
            "quantity": BinanceOrderAdapter._decimal_string(
                intent.quantity
            ),
            "newClientOrderId": client_order_id,
            "newOrderRespType": "FULL",
        }

        if intent.order_type == "LIMIT":
            if intent.reference_price is None:
                raise ValueError(
                    "Reference price is required for LIMIT orders."
                )

            params["price"] = BinanceOrderAdapter._decimal_string(
                intent.reference_price
            )
            params["timeInForce"] = "GTC"

        return params

    def _map_response(
        self,
        *,
        intent: OrderIntent,
        client_order_id: str,
        response: dict[str, Any],
    ) -> OrderExecutionResult:
        exchange_status = str(
            response.get("status", "UNKNOWN")
        ).upper()

        status_map = {
            "FILLED": "FILLED",
            "NEW": "OPEN",
            "PARTIALLY_FILLED": "OPEN",
            "REJECTED": "REJECTED",
            "EXPIRED": "REJECTED",
            "CANCELED": "REJECTED",
        }

        status = status_map.get(exchange_status, "FAILED")

        requested_quantity = self._to_float(
            response.get("origQty"),
            default=intent.quantity,
        )
        filled_quantity = self._to_float(
            response.get("executedQty"),
            default=0.0,
        )

        average_price = self._resolve_average_price(
            response=response,
            filled_quantity=filled_quantity,
        )

        exchange_order_id = response.get("orderId")

        return OrderExecutionResult(
            exchange="BINANCE",
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            status=status,
            client_order_id=str(
                response.get(
                    "clientOrderId",
                    client_order_id,
                )
            ),
            exchange_order_id=(
                str(exchange_order_id)
                if exchange_order_id is not None
                else None
            ),
            requested_quantity=requested_quantity,
            filled_quantity=filled_quantity,
            average_price=average_price,
            simulated=self._testnet,
            message=(
                f"Binance order status: {exchange_status}."
            ),
        )

    @staticmethod
    def _resolve_average_price(
        *,
        response: dict[str, Any],
        filled_quantity: float,
    ) -> float | None:
        fills = response.get("fills")

        if isinstance(fills, list) and fills:
            total_quantity = 0.0
            total_quote = 0.0

            for fill in fills:
                if not isinstance(fill, dict):
                    continue

                quantity = BinanceOrderAdapter._to_float(
                    fill.get("qty"),
                    default=0.0,
                )
                price = BinanceOrderAdapter._to_float(
                    fill.get("price"),
                    default=0.0,
                )

                total_quantity += quantity
                total_quote += quantity * price

            if total_quantity > 0:
                return total_quote / total_quantity

        cumulative_quote = BinanceOrderAdapter._to_float(
            response.get("cummulativeQuoteQty"),
            default=0.0,
        )

        if filled_quantity > 0 and cumulative_quote > 0:
            return cumulative_quote / filled_quantity

        return None

    def _failed(
        self,
        *,
        intent: OrderIntent,
        client_order_id: str,
        message: str,
    ) -> OrderExecutionResult:
        return OrderExecutionResult(
            exchange="BINANCE",
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            status="FAILED",
            client_order_id=client_order_id,
            exchange_order_id=None,
            requested_quantity=intent.quantity,
            filled_quantity=0.0,
            average_price=None,
            simulated=self._testnet,
            message=message,
        )

    @staticmethod
    def _decimal_string(value: float) -> str:
        return format(value, ".16g")

    @staticmethod
    def _to_float(
        value: object,
        *,
        default: float,
    ) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
