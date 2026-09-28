from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.tradinggpt.engine.schemas import (
    OrderRoutingContextRequest,
)
from app.tradinggpt.orders import OrderRoutingContext


def test_default_routing_uses_paper_exchange() -> None:
    routing = OrderRoutingContext()

    assert routing.exchange == "PAPER"
    assert routing.market_type == "SPOT"
    assert routing.order_type == "MARKET"
    assert routing.leverage == 1


@pytest.mark.parametrize(
    "exchange",
    [
        "PAPER",
        "BINANCE",
        "BYBIT",
        "OKX",
    ],
)
def test_schema_accepts_supported_exchanges(
    exchange: str,
) -> None:
    request = OrderRoutingContextRequest(
        exchange=exchange,
        market_type="SPOT",
        order_type="MARKET",
        leverage=1,
    )

    routing = request.to_domain()

    assert routing.exchange == exchange
    assert routing.market_type == "SPOT"
    assert routing.order_type == "MARKET"
    assert routing.leverage == 1


def test_schema_accepts_futures_leverage() -> None:
    request = OrderRoutingContextRequest(
        exchange="BYBIT",
        market_type="FUTURES",
        order_type="MARKET",
        leverage=5,
    )

    routing = request.to_domain()

    assert routing.exchange == "BYBIT"
    assert routing.market_type == "FUTURES"
    assert routing.leverage == 5


def test_schema_rejects_spot_leverage() -> None:
    with pytest.raises(ValidationError):
        OrderRoutingContextRequest(
            exchange="BINANCE",
            market_type="SPOT",
            order_type="MARKET",
            leverage=3,
        )


def test_schema_rejects_unknown_exchange() -> None:
    with pytest.raises(ValidationError):
        OrderRoutingContextRequest(
            exchange="UNKNOWN",
            market_type="SPOT",
            order_type="MARKET",
            leverage=1,
        )
