from __future__ import annotations

from app.tradinggpt.risk.models import (
    AccountRiskContext,
    RiskLimits,
)
from app.tradinggpt.risk.runtime import (
    RuntimeRiskGuard,
)


def safe_account() -> AccountRiskContext:
    return AccountRiskContext(
        equity=10_000.0,
        peak_equity=10_200.0,
        daily_pnl=-100.0,
        open_positions=2,
        current_exposure_value=3_000.0,
        correlated_exposure_value=1_000.0,
    )


def test_guard_allows_safe_account() -> None:
    result = RuntimeRiskGuard.evaluate(
        account=safe_account()
    )

    assert result.status == "ALLOW"
    assert result.trading_allowed is True
    assert result.daily_loss_percent == 1.0
    assert result.total_exposure_percent == 30.0


def test_guard_blocks_daily_loss() -> None:
    account = AccountRiskContext(
        equity=10_000.0,
        peak_equity=10_000.0,
        daily_pnl=-300.0,
        open_positions=1,
        current_exposure_value=1_000.0,
    )

    result = RuntimeRiskGuard.evaluate(
        account=account
    )

    assert result.status == "DENY"
    assert result.trading_allowed is False
    assert (
        "Maximum daily loss limit"
        in result.reasons[0]
    )


def test_guard_blocks_drawdown() -> None:
    account = AccountRiskContext(
        equity=9_000.0,
        peak_equity=10_000.0,
        daily_pnl=0.0,
        open_positions=1,
        current_exposure_value=1_000.0,
    )

    result = RuntimeRiskGuard.evaluate(
        account=account
    )

    assert result.status == "DENY"
    assert result.drawdown_percent == 10.0


def test_guard_blocks_open_position_limit() -> None:
    account = AccountRiskContext(
        equity=10_000.0,
        peak_equity=10_000.0,
        daily_pnl=0.0,
        open_positions=5,
        current_exposure_value=2_000.0,
    )

    result = RuntimeRiskGuard.evaluate(
        account=account
    )

    assert result.status == "DENY"
    assert any(
        "open positions" in reason
        for reason in result.reasons
    )


def test_guard_blocks_exposure_limit() -> None:
    account = AccountRiskContext(
        equity=10_000.0,
        peak_equity=10_000.0,
        daily_pnl=0.0,
        open_positions=2,
        current_exposure_value=8_000.0,
    )

    result = RuntimeRiskGuard.evaluate(
        account=account
    )

    assert result.status == "DENY"
    assert result.total_exposure_percent == 80.0


def test_guard_warns_near_limit() -> None:
    limits = RiskLimits(
        max_daily_loss_percent=3.0,
        max_drawdown_percent=10.0,
        max_total_exposure_percent=80.0,
        max_correlated_exposure_percent=40.0,
        max_open_positions=5,
    )
    account = AccountRiskContext(
        equity=10_000.0,
        peak_equity=10_000.0,
        daily_pnl=-250.0,
        open_positions=2,
        current_exposure_value=6_500.0,
    )

    result = RuntimeRiskGuard.evaluate(
        account=account,
        limits=limits,
    )

    assert result.status == "ALLOW"
    assert len(result.warnings) == 2
