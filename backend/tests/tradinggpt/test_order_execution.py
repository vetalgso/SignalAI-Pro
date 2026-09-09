from __future__ import annotations

import pytest

from app.tradinggpt.orders import (
    OrderExecutionService,
    OrderIntent,
    UnsupportedExchangeError,
)


def build_intent(
    *,
    exchange: str = "PAPER",
    order_type: str = "MARKET",
    reference_price: float | None = 100_000.0,
) -> OrderIntent:
    return OrderIntent(
        exchange=exchange,
        market_type="SPOT",
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


def test_paper_market_order_is_filled() -> None:
    service = OrderExecutionService(
        id_factory=lambda: "test-market",
    )

    result = service.execute(build_intent())

    assert result.status == "FILLED"
    assert result.exchange == "PAPER"
    assert result.client_order_id == "test-market"
    assert result.exchange_order_id == "paper-test-market"
    assert result.filled_quantity == 0.01
    assert result.average_price == 100_000.0
    assert result.simulated is True


def test_paper_limit_order_remains_open() -> None:
    service = OrderExecutionService(
        id_factory=lambda: "test-limit",
    )

    result = service.execute(
        build_intent(order_type="LIMIT"),
    )

    assert result.status == "OPEN"
    assert result.filled_quantity == 0.0
    assert result.average_price is None


def test_paper_order_without_price_is_rejected() -> None:
    service = OrderExecutionService(
        id_factory=lambda: "test-rejected",
    )

    result = service.execute(
        build_intent(reference_price=None),
    )

    assert result.status == "REJECTED"
    assert result.exchange_order_id is None
    assert result.filled_quantity == 0.0


def test_service_reports_supported_exchange() -> None:
    service = OrderExecutionService()

    assert service.supports("PAPER") is True
    assert service.supports("BINANCE") is False


def test_service_rejects_unregistered_exchange() -> None:
    service = OrderExecutionService()

    with pytest.raises(
        UnsupportedExchangeError,
        match="BINANCE",
    ):
        service.execute(
            build_intent(exchange="BINANCE"),
        )
