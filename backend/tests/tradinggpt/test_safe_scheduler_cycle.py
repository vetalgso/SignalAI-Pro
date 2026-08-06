from __future__ import annotations

from app.tradinggpt.risk.models import (
    AccountRiskContext,
    RiskLimits,
)
from app.tradinggpt.scheduler.service import (
    SafeSchedulerCycleService,
)


def safe_account() -> AccountRiskContext:
    return AccountRiskContext(
        equity=10_000.0,
        peak_equity=10_000.0,
        daily_pnl=-50.0,
        open_positions=1,
        current_exposure_value=2_000.0,
        correlated_exposure_value=500.0,
    )


def test_allowed_cycle_executes_as_dry_run() -> None:
    calls: list[bool] = []

    def execute(
        dry_run: bool,
    ) -> dict[str, object]:
        calls.append(dry_run)

        return {
            "action": "DRY_RUN",
            "journal": {
                "status": "DRY_RUN",
            },
        }

    service = SafeSchedulerCycleService(
        execute_callback=execute,
    )

    result = service.run(
        account=safe_account()
    )

    assert result["status"] == "COMPLETED"
    assert result["dry_run"] is True
    assert result["risk"]["status"] == "ALLOW"
    assert result["execution"] is not None
    assert calls == [True]


def test_denied_cycle_never_executes() -> None:
    calls = 0

    def execute(
        dry_run: bool,
    ) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {}

    account = AccountRiskContext(
        equity=10_000.0,
        peak_equity=10_000.0,
        daily_pnl=-400.0,
        open_positions=1,
        current_exposure_value=1_000.0,
    )

    service = SafeSchedulerCycleService(
        execute_callback=execute,
    )

    result = service.run(
        account=account
    )

    assert result["status"] == "BLOCKED"
    assert result["execution"] is None
    assert result["risk"]["status"] == "DENY"
    assert calls == 0


def test_open_position_limit_blocks_cycle() -> None:
    calls = 0

    def execute(
        dry_run: bool,
    ) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {}

    account = AccountRiskContext(
        equity=10_000.0,
        peak_equity=10_000.0,
        daily_pnl=0.0,
        open_positions=5,
        current_exposure_value=2_000.0,
    )

    service = SafeSchedulerCycleService(
        execute_callback=execute,
    )

    result = service.run(
        account=account
    )

    assert result["status"] == "BLOCKED"
    assert calls == 0
    assert any(
        "open positions" in reason
        for reason in result["risk"]["reasons"]
    )


def test_custom_limits_are_applied() -> None:
    calls = 0

    def execute(
        dry_run: bool,
    ) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"dry_run": dry_run}

    limits = RiskLimits(
        max_daily_loss_percent=1.0,
        max_drawdown_percent=10.0,
        max_total_exposure_percent=80.0,
        max_correlated_exposure_percent=40.0,
        max_open_positions=5,
    )

    service = SafeSchedulerCycleService(
        execute_callback=execute,
    )

    result = service.run(
        account=safe_account(),
        limits=limits,
    )

    assert result["status"] == "ALLOW" or (
        result["status"] == "COMPLETED"
    )
    assert calls == 1


def test_callback_result_is_preserved() -> None:
    expected = {
        "action": "SKIPPED",
        "reason": "NO_TRADE",
        "analysis": {"symbol": "BTCUSDT"},
        "journal": None,
    }

    service = SafeSchedulerCycleService(
        execute_callback=lambda dry_run: expected,
    )

    result = service.run(
        account=safe_account()
    )

    assert result["execution"] == expected
    assert result["reason"] is None


def test_runtime_warning_does_not_block() -> None:
    account = AccountRiskContext(
        equity=10_000.0,
        peak_equity=10_000.0,
        daily_pnl=-250.0,
        open_positions=2,
        current_exposure_value=6_500.0,
    )

    service = SafeSchedulerCycleService(
        execute_callback=lambda dry_run: {
            "dry_run": dry_run
        },
    )

    result = service.run(
        account=account
    )

    assert result["status"] == "COMPLETED"
    assert result["risk"]["warnings"]
    assert result["execution"] == {
        "dry_run": True
    }
