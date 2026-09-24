from __future__ import annotations

from typing import Any

import pytest

from app.tradinggpt.portfolio_sync import (
    BinancePortfolioProvider,
    PaperPortfolioProvider,
    PortfolioSyncService,
    UnsupportedPortfolioSourceError,
)


class FakeBinancePortfolioClient:
    def __init__(
        self,
        *,
        account: dict[str, Any],
        open_orders: list[dict[str, Any]],
    ) -> None:
        self.account = account
        self.open_orders = open_orders
        self.account_calls = 0
        self.open_order_calls = 0

    def get_account(
        self,
    ) -> dict[str, Any]:
        self.account_calls += 1
        return self.account

    def get_open_orders(
        self,
        **params: Any,
    ) -> list[dict[str, Any]]:
        self.open_order_calls += 1
        return self.open_orders


def test_paper_snapshot_is_safe_and_empty() -> None:
    provider = PaperPortfolioProvider()

    snapshot = provider.get_snapshot()

    assert snapshot.source == "PAPER"
    assert snapshot.balances == []
    assert snapshot.open_orders == []
    assert snapshot.positions == []
    assert snapshot.total_wallet_balance == 0.0


def test_binance_snapshot_maps_balances_and_orders() -> None:
    client = FakeBinancePortfolioClient(
        account={
            "balances": [
                {
                    "asset": "BTC",
                    "free": "0.01000000",
                    "locked": "0.00200000",
                },
                {
                    "asset": "USDT",
                    "free": "1250.50",
                    "locked": "100.00",
                },
                {
                    "asset": "ZERO",
                    "free": "0",
                    "locked": "0",
                },
            ]
        },
        open_orders=[
            {
                "symbol": "BTCUSDT",
                "orderId": 123,
                "clientOrderId": "portfolio-test",
                "price": "95000.00",
                "origQty": "0.005",
                "executedQty": "0.001",
                "status": "NEW",
                "type": "LIMIT",
                "side": "BUY",
            }
        ],
    )

    provider = BinancePortfolioProvider(
        client=client
    )

    snapshot = provider.get_snapshot()

    assert snapshot.source == "BINANCE"
    assert len(snapshot.balances) == 2
    assert snapshot.balances[0].asset == "BTC"
    assert snapshot.balances[0].total == pytest.approx(
        0.012
    )
    assert snapshot.balances[1].asset == "USDT"

    assert len(snapshot.open_orders) == 1
    order = snapshot.open_orders[0]

    assert order.exchange_order_id == "123"
    assert order.client_order_id == "portfolio-test"
    assert order.symbol == "BTCUSDT"
    assert order.side == "BUY"
    assert order.price == 95_000.0
    assert order.original_quantity == 0.005
    assert order.executed_quantity == 0.001

    assert len(snapshot.positions) == 2
    assert snapshot.positions[0].symbol == "BTC"
    assert snapshot.positions[0].quantity == pytest.approx(
        0.012
    )

    assert client.account_calls == 1
    assert client.open_order_calls == 1


def test_binance_snapshot_skips_invalid_records() -> None:
    client = FakeBinancePortfolioClient(
        account={
            "balances": [
                {
                    "asset": "",
                    "free": "10",
                    "locked": "0",
                },
                "invalid",
                {
                    "asset": "ETH",
                    "free": "bad-value",
                    "locked": "1",
                },
            ]
        },
        open_orders=[
            {
                "symbol": "",
                "orderId": 1,
                "side": "BUY",
            },
            {
                "symbol": "ETHUSDT",
                "orderId": None,
                "side": "SELL",
            },
            {
                "symbol": "ETHUSDT",
                "orderId": 2,
                "side": "INVALID",
            },
        ],
    )

    snapshot = BinancePortfolioProvider(
        client=client
    ).get_snapshot()

    assert len(snapshot.balances) == 1
    assert snapshot.balances[0].asset == "ETH"
    assert snapshot.balances[0].total == 1.0
    assert snapshot.open_orders == []


def test_service_supports_paper_by_default() -> None:
    service = PortfolioSyncService()

    assert service.supports("PAPER") is True
    assert service.supports("BINANCE") is False

    snapshot = service.get_snapshot(
        source="paper"
    )

    assert snapshot.source == "PAPER"


def test_service_registers_binance_provider() -> None:
    client = FakeBinancePortfolioClient(
        account={"balances": []},
        open_orders=[],
    )

    service = PortfolioSyncService(
        providers=[
            PaperPortfolioProvider(),
            BinancePortfolioProvider(
                client=client
            ),
        ]
    )

    assert service.supports("PAPER") is True
    assert service.supports("BINANCE") is True
    assert service.get_snapshot(
        source="BINANCE"
    ).source == "BINANCE"


def test_service_rejects_unknown_source() -> None:
    service = PortfolioSyncService()

    with pytest.raises(
        UnsupportedPortfolioSourceError,
        match="Unsupported portfolio source",
    ):
        service.get_snapshot(
            source="UNKNOWN"
        )
