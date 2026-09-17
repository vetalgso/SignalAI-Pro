from __future__ import annotations

from typing import Any

import pytest

from app.tradinggpt.exchanges.config import (
    ExchangeExecutionSettings,
)
from app.tradinggpt.exchanges.registry import (
    ExchangeAdapterRegistry,
)


class FakeBinanceClient:
    def __init__(self) -> None:
        self.account_calls = 0
        self.open_orders_calls = 0

    def get_account(
        self,
    ) -> dict[str, Any]:
        self.account_calls += 1

        return {
            "balances": [
                {
                    "asset": "BTC",
                    "free": "0.25",
                    "locked": "0.05",
                },
                {
                    "asset": "USDT",
                    "free": "1500",
                    "locked": "100",
                },
            ],
        }

    def get_open_orders(
        self,
        **params: Any,
    ) -> list[dict[str, Any]]:
        self.open_orders_calls += 1

        return [
            {
                "orderId": 123,
                "clientOrderId": "portfolio-test",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "type": "LIMIT",
                "status": "NEW",
                "price": "60000",
                "origQty": "0.01",
                "executedQty": "0",
            },
        ]

    def create_order(
        self,
        **params: Any,
    ) -> dict[str, Any]:
        return {
            "orderId": 456,
            "clientOrderId": "execution-test",
            "symbol": params["symbol"],
            "status": "FILLED",
            "executedQty": params["quantity"],
        }


def enabled_testnet_settings(
) -> ExchangeExecutionSettings:
    return ExchangeExecutionSettings(
        enable_binance_execution=True,
        binance_testnet=True,
        enable_real_trading=False,
        binance_testnet_api_key="test-key",
        binance_testnet_secret_key="test-secret",
    )


def test_registry_keeps_paper_portfolio_available_by_default(
) -> None:
    registry = ExchangeAdapterRegistry(
        settings=ExchangeExecutionSettings(),
    )

    service = registry.build_portfolio_sync_service()

    assert service.supports("PAPER")
    assert not service.supports("BINANCE")


def test_registry_registers_binance_portfolio_provider(
) -> None:
    client = FakeBinanceClient()

    registry = ExchangeAdapterRegistry(
        settings=enabled_testnet_settings(),
        binance_client_factory=lambda settings: client,
    )

    service = registry.build_portfolio_sync_service()

    assert service.supports("PAPER")
    assert service.supports("BINANCE")

    snapshot = service.get_snapshot(
        source="BINANCE"
    )

    assert snapshot.source == "BINANCE"
    assert len(snapshot.balances) == 2
    assert snapshot.balances[0].asset == "BTC"
    assert snapshot.balances[0].total == pytest.approx(0.30)
    assert snapshot.balances[1].asset == "USDT"
    assert snapshot.balances[1].total == pytest.approx(1600.0)

    assert len(snapshot.positions) == 2
    assert snapshot.positions[0].symbol == "BTC"
    assert snapshot.positions[0].quantity == pytest.approx(0.30)

    assert len(snapshot.open_orders) == 1
    assert snapshot.open_orders[0].symbol == "BTCUSDT"
    assert snapshot.open_orders[0].exchange_order_id == "123"

    assert client.account_calls == 1
    assert client.open_orders_calls == 1


def test_registry_reuses_one_binance_client_for_services(
) -> None:
    client = FakeBinanceClient()
    factory_calls = 0

    def client_factory(
        settings: ExchangeExecutionSettings,
    ) -> FakeBinanceClient:
        nonlocal factory_calls
        factory_calls += 1
        return client

    registry = ExchangeAdapterRegistry(
        settings=enabled_testnet_settings(),
        binance_client_factory=client_factory,
    )

    execution_service = registry.build_execution_service()
    portfolio_service = registry.build_portfolio_sync_service()

    assert execution_service.supports("BINANCE")
    assert portfolio_service.supports("BINANCE")
    assert factory_calls == 1


def test_registry_rejects_missing_binance_credentials_for_portfolio(
) -> None:
    settings = ExchangeExecutionSettings(
        enable_binance_execution=True,
        binance_testnet=True,
    )

    registry = ExchangeAdapterRegistry(
        settings=settings,
        binance_client_factory=lambda current: (
            FakeBinanceClient()
        ),
    )

    with pytest.raises(
        ValueError,
        match="credentials are missing",
    ):
        registry.build_portfolio_sync_service()


def test_registry_rejects_live_portfolio_without_safety_switch(
) -> None:
    settings = ExchangeExecutionSettings(
        enable_binance_execution=True,
        binance_testnet=False,
        enable_real_trading=False,
        binance_api_key="live-key",
        binance_secret_key="live-secret",
    )

    registry = ExchangeAdapterRegistry(
        settings=settings,
        binance_client_factory=lambda current: (
            FakeBinanceClient()
        ),
    )

    with pytest.raises(
        ValueError,
        match="ENABLE_REAL_TRADING=true",
    ):
        registry.build_portfolio_sync_service()
