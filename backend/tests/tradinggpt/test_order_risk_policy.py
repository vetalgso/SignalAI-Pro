from __future__ import annotations

import pytest

from app.tradinggpt.orders.execution_models import (
    OrderExecutionResult,
)
from app.tradinggpt.orders.risk import (
    OrderRiskPolicy,
    OrderRiskUsage,
    OrderRiskUsageUnavailableError,
    count_verified_open_orders,
)
from app.tradinggpt.orders.validation_models import (
    OrderPreviewResult,
)


def build_preview(
    *,
    symbol: str = "BTCUSDT",
    notional: float | None = 50.0,
    valid: bool = True,
) -> OrderPreviewResult:
    return OrderPreviewResult(
        exchange="BINANCE",
        symbol=symbol,
        side="BUY",
        order_type="MARKET",
        valid=valid,
        requested_quantity=0.001,
        normalized_quantity=0.001,
        requested_price=50_000.0,
        normalized_price=50_000.0,
        estimated_notional=notional,
        available_balance=1_000.0,
        balance_asset="USDT",
        errors=(
            []
            if valid
            else ["Exchange validation failed."]
        ),
        warnings=[],
    )


def test_policy_allows_order_within_limits(
) -> None:
    policy = OrderRiskPolicy.configured(
        execution_enabled=True,
        max_order_notional=100.0,
        allowed_symbols=(
            " btcusdt, ETHUSDT "
        ),
    )

    result = policy.apply(
        build_preview()
    )

    assert result.valid is True
    assert result.errors == []


def test_policy_blocks_disabled_execution(
) -> None:
    policy = OrderRiskPolicy.configured(
        execution_enabled=False,
        max_order_notional=100.0,
        allowed_symbols="",
    )

    result = policy.apply(
        build_preview()
    )

    assert result.valid is False
    assert result.errors == [
        (
            "TESTNET order execution is "
            "disabled by risk policy."
        )
    ]


def test_policy_blocks_disallowed_symbol(
) -> None:
    policy = OrderRiskPolicy.configured(
        execution_enabled=True,
        max_order_notional=100.0,
        allowed_symbols="ETHUSDT",
    )

    result = policy.apply(
        build_preview(
            symbol="BTCUSDT"
        )
    )

    assert result.valid is False
    assert "BTCUSDT" in result.errors[0]


def test_policy_blocks_excessive_notional(
) -> None:
    policy = OrderRiskPolicy.configured(
        execution_enabled=True,
        max_order_notional=100.0,
        allowed_symbols="",
    )

    result = policy.apply(
        build_preview(
            notional=100.01
        )
    )

    assert result.valid is False
    assert "exceeds" in result.errors[0]
    assert "100.00000000" in result.errors[0]


def test_policy_fails_closed_without_notional(
) -> None:
    policy = OrderRiskPolicy.configured(
        execution_enabled=True,
        max_order_notional=100.0,
        allowed_symbols="",
    )

    result = policy.apply(
        build_preview(
            notional=None
        )
    )

    assert result.valid is False
    assert "could not be estimated" in (
        result.errors[0]
    )


def test_policy_preserves_invalid_preview(
) -> None:
    policy = OrderRiskPolicy.configured(
        execution_enabled=False,
        max_order_notional=100.0,
        allowed_symbols="ETHUSDT",
    )

    preview = build_preview(
        valid=False
    )
    result = policy.apply(preview)

    assert result is preview
    assert result.errors == [
        "Exchange validation failed."
    ]



def test_policy_blocks_projected_daily_notional(
) -> None:
    policy = OrderRiskPolicy.configured(
        execution_enabled=True,
        max_order_notional=100.0,
        max_daily_notional=500.0,
        max_open_orders=5,
        allowed_symbols="",
    )

    result = policy.apply(
        build_preview(notional=50.0),
        usage=OrderRiskUsage(
            daily_notional=460.0,
            open_orders=1,
        ),
    )

    assert result.valid is False
    assert "Projected daily notional" in (
        result.errors[0]
    )
    assert "510.00000000" in result.errors[0]


def test_policy_blocks_open_order_limit(
) -> None:
    policy = OrderRiskPolicy.configured(
        execution_enabled=True,
        max_order_notional=100.0,
        max_daily_notional=500.0,
        max_open_orders=5,
        allowed_symbols="",
    )

    result = policy.apply(
        build_preview(notional=50.0),
        usage=OrderRiskUsage(
            daily_notional=100.0,
            open_orders=5,
        ),
    )

    assert result.valid is False
    assert "Open order count 5" in (
        result.errors[0]
    )


def test_policy_allows_projected_usage_at_limits(
) -> None:
    policy = OrderRiskPolicy.configured(
        execution_enabled=True,
        max_order_notional=100.0,
        max_daily_notional=500.0,
        max_open_orders=5,
        allowed_symbols="",
    )

    result = policy.apply(
        build_preview(notional=50.0),
        usage=OrderRiskUsage(
            daily_notional=450.0,
            open_orders=4,
        ),
    )

    assert result.valid is True


def test_reduce_only_bypasses_account_usage_limits(
) -> None:
    policy = OrderRiskPolicy.configured(
        execution_enabled=True,
        max_order_notional=100.0,
        max_daily_notional=500.0,
        max_open_orders=5,
        allowed_symbols="",
    )

    result = policy.apply(
        build_preview(notional=50.0),
        usage=OrderRiskUsage(
            daily_notional=500.0,
            open_orders=5,
        ),
        increases_exposure=False,
    )

    assert result.valid is True



def test_verified_open_order_count_accepts_only_open(
) -> None:
    results = [
        OrderExecutionResult(
            exchange="BINANCE",
            symbol="BTCUSDT",
            side="BUY",
            order_type="LIMIT",
            status="OPEN",
            client_order_id="client-1",
            exchange_order_id="1001",
            requested_quantity=0.001,
            filled_quantity=0.0,
            average_price=None,
            simulated=True,
            message="Open.",
        ),
        OrderExecutionResult(
            exchange="BINANCE",
            symbol="ETHUSDT",
            side="SELL",
            order_type="LIMIT",
            status="PARTIALLY_FILLED",
            client_order_id="client-2",
            exchange_order_id="1002",
            requested_quantity=0.01,
            filled_quantity=0.002,
            average_price=3000.0,
            simulated=True,
            message="Partially filled.",
        ),
    ]

    assert count_verified_open_orders(
        results
    ) == 2


def test_verified_open_order_count_fails_closed(
) -> None:
    result = OrderExecutionResult(
        exchange="BINANCE",
        symbol="",
        side="BUY",
        order_type="LIMIT",
        status="FAILED",
        client_order_id="",
        exchange_order_id=None,
        requested_quantity=0.0,
        filled_quantity=0.0,
        average_price=None,
        simulated=True,
        message="Remote request failed.",
    )

    with pytest.raises(
        OrderRiskUsageUnavailableError,
        match="could not be verified",
    ):
        count_verified_open_orders(
            [result]
        )
