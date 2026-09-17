from __future__ import annotations

from typing import Any

from app.tradinggpt.orders import (
    BinanceOrderAdapter,
    OrderExecutionService,
    OrderIntent,
)


class FakeBinanceClient:
    def __init__(
        self,
        *,
        response: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response or {}
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def create_order(
        self,
        **params: Any,
    ) -> dict[str, Any]:
        self.calls.append(params)

        if self.error is not None:
            raise self.error

        return self.response

    def get_symbol_info(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "status": "TRADING",
            "baseAsset": "BTC",
            "quoteAsset": "USDT",
            "filters": [
                {
                    "filterType": "LOT_SIZE",
                    "minQty": "0.00001",
                    "maxQty": "9000",
                    "stepSize": "0.00001",
                },
                {
                    "filterType": "PRICE_FILTER",
                    "minPrice": "0.01",
                    "maxPrice": "1000000",
                    "tickSize": "0.01",
                },
                {
                    "filterType": "MIN_NOTIONAL",
                    "minNotional": "5",
                },
            ],
        }

    def get_symbol_ticker(
        self,
        **params: Any,
    ) -> dict[str, Any]:
        return {
            "symbol": params["symbol"],
            "price": "100000",
        }

    def get_asset_balance(
        self,
        **params: Any,
    ) -> dict[str, Any]:
        return {
            "asset": params["asset"],
            "free": "1000000",
            "locked": "0",
        }


def build_intent(
    *,
    order_type: str = "MARKET",
    market_type: str = "SPOT",
    reference_price: float | None = 100_000.0,
) -> OrderIntent:
    return OrderIntent(
        exchange="BINANCE",
        market_type=market_type,
        symbol="BTCUSDT",
        side="BUY",
        order_type=order_type,
        quantity=0.01,
        reference_price=reference_price,
        stop_loss=98_500.0,
        take_profit_1=102_000.0,
        take_profit_2=104_000.0,
        leverage=1,
        reduce_only=False,
    )


def test_binance_market_order_is_mapped_to_filled() -> None:
    client = FakeBinanceClient(
        response={
            "symbol": "BTCUSDT",
            "orderId": 12345,
            "clientOrderId": "test-market",
            "status": "FILLED",
            "origQty": "0.01000000",
            "executedQty": "0.01000000",
            "cummulativeQuoteQty": "1000.00000000",
            "fills": [
                {
                    "price": "100000.00000000",
                    "qty": "0.01000000",
                }
            ],
        }
    )

    service = OrderExecutionService(
        adapters=[
            BinanceOrderAdapter(
                client=client,
                testnet=True,
            )
        ],
        id_factory=lambda: "test-market",
    )

    result = service.execute(build_intent())

    assert result.exchange == "BINANCE"
    assert result.status == "FILLED"
    assert result.exchange_order_id == "12345"
    assert result.client_order_id == "test-market"
    assert result.filled_quantity == 0.01
    assert result.average_price == 100_000.0
    assert result.simulated is True

    assert client.calls == [
        {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "quantity": "0.01",
            "newClientOrderId": "test-market",
            "newOrderRespType": "FULL",
        }
    ]


def test_binance_limit_order_uses_gtc_and_price() -> None:
    client = FakeBinanceClient(
        response={
            "orderId": 777,
            "clientOrderId": "test-limit",
            "status": "NEW",
            "origQty": "0.01",
            "executedQty": "0",
            "cummulativeQuoteQty": "0",
        }
    )

    adapter = BinanceOrderAdapter(
        client=client,
        testnet=True,
    )
    service = OrderExecutionService(
        adapters=[adapter],
        id_factory=lambda: "test-limit",
    )

    result = service.execute(
        build_intent(order_type="LIMIT")
    )

    assert result.status == "OPEN"
    assert result.average_price is None

    call = client.calls[0]

    assert call["type"] == "LIMIT"
    assert call["price"] == "100000"
    assert call["timeInForce"] == "GTC"


def test_binance_limit_order_without_price_fails() -> None:
    client = FakeBinanceClient()

    adapter = BinanceOrderAdapter(
        client=client,
        testnet=True,
    )

    result = adapter.execute(
        intent=build_intent(
            order_type="LIMIT",
            reference_price=None,
        ),
        client_order_id="missing-price",
    )

    assert result.status == "FAILED"
    assert result.exchange_order_id is None
    assert "LIMIT order requires a price" in result.message
    assert client.calls == []


def test_binance_client_error_returns_failed_result() -> None:
    client = FakeBinanceClient(
        error=RuntimeError("testnet unavailable")
    )

    adapter = BinanceOrderAdapter(
        client=client,
        testnet=True,
    )

    result = adapter.execute(
        intent=build_intent(),
        client_order_id="failed-order",
    )

    assert result.status == "FAILED"
    assert result.filled_quantity == 0.0
    assert "testnet unavailable" in result.message


def test_binance_adapter_rejects_futures_for_now() -> None:
    client = FakeBinanceClient()

    adapter = BinanceOrderAdapter(
        client=client,
        testnet=True,
    )

    result = adapter.execute(
        intent=build_intent(market_type="FUTURES"),
        client_order_id="futures-order",
    )

    assert result.status == "FAILED"
    assert "futures" in result.message.lower()
    assert client.calls == []


def test_binance_is_not_enabled_by_default() -> None:
    service = OrderExecutionService()

    assert service.supports("PAPER") is True
    assert service.supports("BINANCE") is False
