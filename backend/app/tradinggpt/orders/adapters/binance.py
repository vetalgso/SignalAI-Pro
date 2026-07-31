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

    def get_order(
        self,
        **params: Any,
    ) -> dict[str, Any]:
        """Fetch a Binance spot order."""

    def cancel_order(
        self,
        **params: Any,
    ) -> dict[str, Any]:
        """Cancel a Binance spot order."""

    def get_open_orders(
        self,
        **params: Any,
    ) -> list[dict[str, Any]]:
        """Fetch open Binance spot orders."""


class BinanceOrderAdapter:
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
                symbol=intent.symbol,
                side=intent.side,
                order_type=intent.order_type,
                client_order_id=client_order_id,
                exchange_order_id=None,
                requested_quantity=intent.quantity,
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
                symbol=intent.symbol,
                side=intent.side,
                order_type=intent.order_type,
                client_order_id=client_order_id,
                exchange_order_id=None,
                requested_quantity=intent.quantity,
                message=f"Binance order failed: {exc}",
            )

        return self._map_response(
            response=response,
            fallback_symbol=intent.symbol,
            fallback_side=intent.side,
            fallback_order_type=intent.order_type,
            fallback_client_order_id=client_order_id,
            fallback_quantity=intent.quantity,
            message_prefix="Binance order status",
        )

    def get_order(
        self,
        *,
        symbol: str,
        order_id: str,
    ) -> OrderExecutionResult:
        try:
            response = self._client.get_order(
                symbol=symbol,
                orderId=order_id,
            )
        except Exception as exc:
            return self._failed(
                symbol=symbol,
                side="BUY",
                order_type="LIMIT",
                client_order_id="",
                exchange_order_id=order_id,
                requested_quantity=0.0,
                message=f"Binance get order failed: {exc}",
            )

        return self._map_response(
            response=response,
            fallback_symbol=symbol,
            fallback_side="BUY",
            fallback_order_type="LIMIT",
            fallback_client_order_id="",
            fallback_quantity=0.0,
            message_prefix="Binance order status",
        )

    def cancel_order(
        self,
        *,
        symbol: str,
        order_id: str,
    ) -> OrderExecutionResult:
        try:
            response = self._client.cancel_order(
                symbol=symbol,
                orderId=order_id,
            )
        except Exception as exc:
            return self._failed(
                symbol=symbol,
                side="BUY",
                order_type="LIMIT",
                client_order_id="",
                exchange_order_id=order_id,
                requested_quantity=0.0,
                message=f"Binance cancel order failed: {exc}",
            )

        return self._map_response(
            response=response,
            fallback_symbol=symbol,
            fallback_side="BUY",
            fallback_order_type="LIMIT",
            fallback_client_order_id="",
            fallback_quantity=0.0,
            message_prefix="Binance cancel status",
        )

    def list_open_orders(
        self,
        *,
        symbol: str | None = None,
    ) -> list[OrderExecutionResult]:
        params: dict[str, object] = {}

        if symbol:
            params["symbol"] = symbol

        try:
            responses = self._client.get_open_orders(**params)
        except Exception as exc:
            return [
                self._failed(
                    symbol=symbol or "",
                    side="BUY",
                    order_type="LIMIT",
                    client_order_id="",
                    exchange_order_id=None,
                    requested_quantity=0.0,
                    message=f"Binance open orders failed: {exc}",
                )
            ]

        return [
            self._map_response(
                response=response,
                fallback_symbol=symbol or "",
                fallback_side="BUY",
                fallback_order_type="LIMIT",
                fallback_client_order_id="",
                fallback_quantity=0.0,
                message_prefix="Binance order status",
            )
            for response in responses
        ]

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
        response: dict[str, Any],
        fallback_symbol: str,
        fallback_side: str,
        fallback_order_type: str,
        fallback_client_order_id: str,
        fallback_quantity: float,
        message_prefix: str,
    ) -> OrderExecutionResult:
        exchange_status = str(
            response.get("status", "UNKNOWN")
        ).upper()

        status_map = {
            "FILLED": "FILLED",
            "NEW": "OPEN",
            "PARTIALLY_FILLED": "PARTIALLY_FILLED",
            "CANCELED": "CANCELED",
            "REJECTED": "REJECTED",
            "EXPIRED": "REJECTED",
            "EXPIRED_IN_MATCH": "REJECTED",
        }

        status = status_map.get(exchange_status, "FAILED")

        requested_quantity = self._to_float(
            response.get("origQty"),
            default=fallback_quantity,
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

        client_order_id = (
            response.get("clientOrderId")
            or response.get("origClientOrderId")
            or fallback_client_order_id
        )

        return OrderExecutionResult(
            exchange="BINANCE",
            symbol=str(
                response.get("symbol", fallback_symbol)
            ),
            side=str(
                response.get("side", fallback_side)
            ).upper(),
            order_type=str(
                response.get("type", fallback_order_type)
            ).upper(),
            status=status,
            client_order_id=str(client_order_id),
            exchange_order_id=(
                str(exchange_order_id)
                if exchange_order_id is not None
                else None
            ),
            requested_quantity=requested_quantity,
            filled_quantity=filled_quantity,
            average_price=average_price,
            simulated=self._testnet,
            message=f"{message_prefix}: {exchange_status}.",
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
        symbol: str,
        side: str,
        order_type: str,
        client_order_id: str,
        exchange_order_id: str | None,
        requested_quantity: float,
        message: str,
    ) -> OrderExecutionResult:
        return OrderExecutionResult(
            exchange="BINANCE",
            symbol=symbol,
            side=side,
            order_type=order_type,
            status="FAILED",
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            requested_quantity=requested_quantity,
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
