from __future__ import annotations

from app.tradinggpt.execution import ExecutionPlan
from app.tradinggpt.risk import (
    AccountRiskContext,
    RiskLimits,
    RiskManager,
)


def make_execution_plan(
    *,
    status: str = "READY",
    position_quantity: float = 0.025,
    position_value: float = 2_500.0,
    actual_risk_amount: float = 37.5,
) -> ExecutionPlan:
    return ExecutionPlan(
        status=status,
        symbol="BTCUSDT",
        side="LONG",
        recommendation="BUY",
        entry_price=100_000.0,
        stop_loss=98_500.0,
        take_profit_1=102_250.0,
        take_profit_2=103_750.0,
        stop_distance=1_500.0,
        stop_distance_percent=1.5,
        risk_reward_1=1.5,
        risk_reward_2=2.5,
        risk_budget=125.0,
        position_quantity=position_quantity,
        position_value=position_value,
        actual_risk_amount=actual_risk_amount,
        actual_risk_percent=0.375,
        position_cap_applied=True,
        reasons=(),
        warnings=(),
    )


def test_risk_manager_allows_safe_trade() -> None:
    decision = RiskManager.evaluate(
        execution_plan=make_execution_plan(),
        account=AccountRiskContext(
            equity=10_000.0,
            peak_equity=10_000.0,
            daily_pnl=-50.0,
            open_positions=1,
            current_exposure_value=2_000.0,
            correlated_exposure_value=500.0,
        ),
    )

    assert decision.status == "ALLOW"
    assert decision.allowed is True
    assert decision.approved_position_quantity == 0.025
    assert decision.approved_position_value == 2_500.0
    assert decision.approved_risk_amount == 37.5
    assert decision.size_multiplier == 1.0
    assert decision.exposure_percent_after == 45.0


def test_risk_manager_reduces_position_for_exposure() -> None:
    decision = RiskManager.evaluate(
        execution_plan=make_execution_plan(),
        account=AccountRiskContext(
            equity=10_000.0,
            peak_equity=10_000.0,
            daily_pnl=0.0,
            open_positions=2,
            current_exposure_value=7_000.0,
            correlated_exposure_value=1_000.0,
        ),
        limits=RiskLimits(
            max_total_exposure_percent=80.0,
            max_correlated_exposure_percent=50.0,
        ),
    )

    assert decision.status == "REDUCE_SIZE"
    assert decision.allowed is True
    assert decision.size_multiplier == 0.4
    assert decision.approved_position_quantity == 0.01
    assert decision.approved_position_value == 1_000.0
    assert decision.approved_risk_amount == 15.0
    assert decision.exposure_percent_after == 80.0


def test_risk_manager_denies_after_daily_loss_limit() -> None:
    decision = RiskManager.evaluate(
        execution_plan=make_execution_plan(),
        account=AccountRiskContext(
            equity=10_000.0,
            peak_equity=10_000.0,
            daily_pnl=-300.0,
            open_positions=1,
            current_exposure_value=2_000.0,
        ),
    )

    assert decision.status == "DENY"
    assert decision.allowed is False
    assert decision.daily_loss_percent == 3.0
    assert decision.approved_position_value == 0.0
    assert (
        "Maximum daily loss limit has been reached."
        in decision.reasons
    )


def test_risk_manager_denies_after_drawdown_limit() -> None:
    decision = RiskManager.evaluate(
        execution_plan=make_execution_plan(),
        account=AccountRiskContext(
            equity=9_000.0,
            peak_equity=10_000.0,
            daily_pnl=0.0,
            open_positions=1,
            current_exposure_value=2_000.0,
        ),
    )

    assert decision.status == "DENY"
    assert decision.drawdown_percent == 10.0
    assert (
        "Maximum account drawdown limit has been reached."
        in decision.reasons
    )


def test_risk_manager_denies_at_max_open_positions() -> None:
    decision = RiskManager.evaluate(
        execution_plan=make_execution_plan(),
        account=AccountRiskContext(
            equity=10_000.0,
            peak_equity=10_000.0,
            daily_pnl=0.0,
            open_positions=5,
            current_exposure_value=2_000.0,
        ),
    )

    assert decision.status == "DENY"
    assert (
        "Maximum number of open positions has been reached."
        in decision.reasons
    )


def test_risk_manager_denies_correlated_exposure() -> None:
    decision = RiskManager.evaluate(
        execution_plan=make_execution_plan(),
        account=AccountRiskContext(
            equity=10_000.0,
            peak_equity=10_000.0,
            daily_pnl=0.0,
            open_positions=2,
            current_exposure_value=4_000.0,
            correlated_exposure_value=4_000.0,
        ),
    )

    assert decision.status == "DENY"
    assert (
        "Maximum correlated exposure has been reached."
        in decision.reasons
    )


def test_risk_manager_denies_non_ready_plan() -> None:
    decision = RiskManager.evaluate(
        execution_plan=make_execution_plan(
            status="SKIP",
            position_quantity=0.0,
            position_value=0.0,
            actual_risk_amount=0.0,
        ),
        account=AccountRiskContext(
            equity=10_000.0,
            peak_equity=10_000.0,
            daily_pnl=0.0,
            open_positions=0,
            current_exposure_value=0.0,
        ),
    )

    assert decision.status == "DENY"
    assert decision.allowed is False
    assert (
        "Execution plan is not ready for trading."
        in decision.reasons
    )
