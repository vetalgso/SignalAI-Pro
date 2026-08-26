from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.tradinggpt.orders.models import (
    OrderIntent,
)
from app.tradinggpt.orders.risk import (
    OrderRiskPolicy,
)
from app.tradinggpt.orders.signal_order_orchestrator import (
    SignalOrderIneligibleError,
    SignalOrderNotFoundError,
    SignalToOrderOrchestrator,
)
from app.tradinggpt.orders.validation_models import (
    OrderPreviewResult,
)


NOW = datetime(
    2026,
    8,
    26,
    6,
    0,
    tzinfo=timezone.utc,
)


def build_signal(
    **overrides: object,
) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": 41,
        "exchange": "BINANCE",
        "market_type": "SPOT",
        "symbol": "btcusdt",
        "timeframe": "1h",
        "side": "LONG",
        "strategy": "trend_momentum",
        "status": "ACTIVE",
        "confidence": Decimal("82.5"),
        "risk_level": "MEDIUM",
        "entry_min": Decimal("99"),
        "entry_max": Decimal("101"),
        "stop_loss": Decimal("95"),
        "take_profit_1": Decimal("110"),
        "take_profit_2": Decimal("115"),
        "take_profit_3": Decimal("120"),
        "expires_at": (
            NOW + timedelta(hours=1)
        ),
    }
    values.update(overrides)

    return SimpleNamespace(**values)


class FakeSignals:
    def __init__(
        self,
        signal: SimpleNamespace | None,
    ) -> None:
        self.signal = signal
        self.calls: list[int] = []

    def get(
        self,
        signal_id: int,
    ) -> SimpleNamespace | None:
        self.calls.append(signal_id)
        return self.signal


class FakeExecutionService:
    def __init__(self) -> None:
        self.preview_calls: list[
            OrderIntent
        ] = []

    def preview(
        self,
        intent: OrderIntent,
    ) -> OrderPreviewResult:
        self.preview_calls.append(intent)

        price = intent.reference_price
        notional = (
            intent.quantity * price
            if price is not None
            else None
        )

        return OrderPreviewResult(
            exchange=intent.exchange,
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            valid=True,
            requested_quantity=(
                intent.quantity
            ),
            normalized_quantity=(
                intent.quantity
            ),
            requested_price=price,
            normalized_price=price,
            estimated_notional=notional,
            available_balance=10000.0,
            balance_asset="USDT",
            errors=[],
            warnings=[],
        )


def build_orchestrator(
    signal: SimpleNamespace | None,
    *,
    risk_policy: (
        OrderRiskPolicy | None
    ) = None,
) -> tuple[
    SignalToOrderOrchestrator,
    FakeSignals,
    FakeExecutionService,
]:
    signals = FakeSignals(signal)
    execution = FakeExecutionService()

    orchestrator = (
        SignalToOrderOrchestrator(
            signals=signals,
            execution_service=execution,
            risk_policy=(
                risk_policy
                or OrderRiskPolicy()
            ),
            clock=lambda: NOW,
        )
    )

    return (
        orchestrator,
        signals,
        execution,
    )


def test_builds_spot_long_limit_preview(
) -> None:
    orchestrator, signals, execution = (
        build_orchestrator(
            build_signal()
        )
    )

    plan = orchestrator.preview(
        signal_id=41,
        quantity=0.25,
    )

    assert signals.calls == [41]
    assert len(execution.preview_calls) == 1

    intent = execution.preview_calls[0]

    assert intent.exchange == "BINANCE"
    assert intent.market_type == "SPOT"
    assert intent.symbol == "BTCUSDT"
    assert intent.side == "BUY"
    assert intent.order_type == "LIMIT"
    assert intent.quantity == 0.25
    assert intent.reference_price == 101.0
    assert intent.stop_loss == 95.0
    assert intent.take_profit_1 == 110.0
    assert intent.take_profit_2 == 115.0
    assert intent.leverage == 1
    assert intent.reduce_only is False

    assert plan.signal_id == 41
    assert plan.signal_status == "ACTIVE"
    assert plan.preview.valid is True
    assert (
        plan.preview.estimated_notional
        == 25.25
    )

    payload = plan.to_dict()

    assert payload["signal_id"] == 41
    assert payload["strategy"] == (
        "trend_momentum"
    )
    assert payload["confidence"] == 82.5


def test_risk_policy_can_block_preview(
) -> None:
    orchestrator, _, execution = (
        build_orchestrator(
            build_signal(),
            risk_policy=OrderRiskPolicy(
                max_order_notional=50.0,
            ),
        )
    )

    plan = orchestrator.preview(
        signal_id=41,
        quantity=1.0,
    )

    assert len(execution.preview_calls) == 1
    assert plan.preview.valid is False
    assert any(
        "exceeds TESTNET risk limit"
        in error
        for error in plan.preview.errors
    )


@pytest.mark.parametrize(
    "signal_status",
    [
        "TP1_REACHED",
        "STOPPED",
        "EXPIRED",
        "CANCELLED",
    ],
)
def test_rejects_ineligible_status(
    signal_status: str,
) -> None:
    orchestrator, _, execution = (
        build_orchestrator(
            build_signal(
                status=signal_status
            )
        )
    )

    with pytest.raises(
        SignalOrderIneligibleError,
        match="status is not eligible",
    ):
        orchestrator.preview(
            signal_id=41,
            quantity=0.1,
        )

    assert execution.preview_calls == []


def test_accepts_entry_reached_signal(
) -> None:
    orchestrator, _, execution = (
        build_orchestrator(
            build_signal(
                status="ENTRY_REACHED"
            )
        )
    )

    plan = orchestrator.preview(
        signal_id=41,
        quantity=0.1,
    )

    assert plan.signal_status == (
        "ENTRY_REACHED"
    )
    assert len(execution.preview_calls) == 1


def test_rejects_expired_signal(
) -> None:
    orchestrator, _, execution = (
        build_orchestrator(
            build_signal(
                expires_at=(
                    NOW - timedelta(seconds=1)
                )
            )
        )
    )

    with pytest.raises(
        SignalOrderIneligibleError,
        match="has expired",
    ):
        orchestrator.preview(
            signal_id=41,
            quantity=0.1,
        )

    assert execution.preview_calls == []


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"side": "SHORT"},
            "SPOT SHORT",
        ),
        (
            {"market_type": "FUTURES"},
            "Only SPOT",
        ),
        (
            {"exchange": "BYBIT"},
            "Only BINANCE",
        ),
    ],
)
def test_rejects_unsupported_signal_scope(
    overrides: dict[str, object],
    message: str,
) -> None:
    orchestrator, _, execution = (
        build_orchestrator(
            build_signal(**overrides)
        )
    )

    with pytest.raises(
        SignalOrderIneligibleError,
        match=message,
    ):
        orchestrator.preview(
            signal_id=41,
            quantity=0.1,
        )

    assert execution.preview_calls == []


@pytest.mark.parametrize(
    "quantity",
    [
        0.0,
        -1.0,
        float("nan"),
        float("inf"),
    ],
)
def test_rejects_invalid_quantity(
    quantity: float,
) -> None:
    orchestrator, signals, execution = (
        build_orchestrator(
            build_signal()
        )
    )

    with pytest.raises(
        SignalOrderIneligibleError,
        match="finite positive",
    ):
        orchestrator.preview(
            signal_id=41,
            quantity=quantity,
        )

    assert signals.calls == []
    assert execution.preview_calls == []


def test_missing_signal_fails_closed(
) -> None:
    orchestrator, signals, execution = (
        build_orchestrator(None)
    )

    with pytest.raises(
        SignalOrderNotFoundError,
        match="was not found",
    ):
        orchestrator.preview(
            signal_id=999,
            quantity=0.1,
        )

    assert signals.calls == [999]
    assert execution.preview_calls == []
