from __future__ import annotations

from dataclasses import replace

import pytest

from app.tradinggpt.conviction.models import (
    ConvictionFactors,
    ConvictionResult,
)
from app.tradinggpt.engine.schemas import (
    TradingGPTAnalyzeRequest,
)
from app.tradinggpt.execution import (
    ExecutionPlanner,
    MarketExecutionContext,
)


def build_conviction(
    *,
    recommendation: str = "BUY",
    multiplier: float = 1.25,
) -> ConvictionResult:
    return ConvictionResult(
        score=76.5,
        level="HIGH",
        recommendation=recommendation,
        confidence=0.765,
        position_multiplier=multiplier,
        factors=ConvictionFactors(
            signal_score=80.0,
            market_score=75.0,
            portfolio_score=70.0,
            quality_score=80.0,
        ),
    )


def test_execution_planner_builds_ready_plan(
    analyze_request: TradingGPTAnalyzeRequest,
) -> None:
    portfolio = (
        analyze_request.portfolio.to_domain()
    )

    plan = ExecutionPlanner.build(
        conviction=build_conviction(),
        portfolio=portfolio,
        market=MarketExecutionContext(
            symbol="BTCUSDT",
            current_price=100_000.0,
            atr=1_000.0,
            quantity_step=0.000001,
            price_tick=0.1,
        ),
    )

    assert plan.status == "READY"
    assert plan.side == "LONG"
    assert plan.entry_price == 100_000.0
    assert plan.stop_loss == 98_500.0
    assert plan.take_profit_1 == 102_250.0
    assert plan.take_profit_2 == 103_750.0

    assert plan.risk_budget == 125.0
    assert plan.position_cap_applied is True

    assert plan.position_quantity == 0.025
    assert plan.position_value == 2_500.0
    assert plan.actual_risk_amount == 37.5
    assert plan.actual_risk_percent == 0.375


def test_execution_planner_skips_hold_recommendation(
    analyze_request: TradingGPTAnalyzeRequest,
) -> None:
    plan = ExecutionPlanner.build(
        conviction=build_conviction(
            recommendation="HOLD",
            multiplier=1.0,
        ),
        portfolio=(
            analyze_request.portfolio.to_domain()
        ),
        market=MarketExecutionContext(
            symbol="ETHUSDT",
            current_price=4_000.0,
            atr=80.0,
        ),
    )

    assert plan.status == "SKIP"
    assert plan.side == "NONE"
    assert plan.position_quantity == 0.0
    assert plan.entry_price is None


def test_execution_planner_skips_without_capital(
    analyze_request: TradingGPTAnalyzeRequest,
) -> None:
    portfolio = replace(
        analyze_request.portfolio.to_domain(),
        capital=None,
    )

    plan = ExecutionPlanner.build(
        conviction=build_conviction(),
        portfolio=portfolio,
        market=MarketExecutionContext(
            symbol="BTCUSDT",
            current_price=100_000.0,
            atr=1_000.0,
        ),
    )

    assert plan.status == "SKIP"
    assert "capital" in plan.reasons[0].lower()


def test_execution_planner_rejects_invalid_market_data(
    analyze_request: TradingGPTAnalyzeRequest,
) -> None:
    with pytest.raises(
        ValueError,
        match="current_price",
    ):
        ExecutionPlanner.build(
            conviction=build_conviction(),
            portfolio=(
                analyze_request.portfolio.to_domain()
            ),
            market=MarketExecutionContext(
                symbol="BTCUSDT",
                current_price=0.0,
                atr=1_000.0,
            ),
        )
