from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any
from urllib.request import Request, urlopen
from uuid import uuid4

from sqlalchemy import func, select

from app.database.session import SessionLocal
from app.models.scheduler_cycle import SchedulerCycle
from app.models.trading_order import TradingOrder


API_ROOT = "http://localhost:8000"
TEST_INTERVAL_SECONDS = 60
EXECUTION_TIMEOUT_SECONDS = 95


def api_request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None
    headers: dict[str, str] = {}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(
        f"{API_ROOT}{path}",
        data=data,
        headers=headers,
        method=method,
    )

    with urlopen(request, timeout=15) as response:
        body = response.read().decode("utf-8")

    return json.loads(body) if body else {}


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).astimezone(timezone.utc)


def scheduler_cycle_max_id() -> int:
    with SessionLocal() as session:
        result = session.scalar(
            select(
                func.coalesce(
                    func.max(SchedulerCycle.id),
                    0,
                )
            )
        )

    return int(result or 0)


def scheduler_cycle_count_after(
    cycle_id: int,
) -> int:
    with SessionLocal() as session:
        result = session.scalar(
            select(func.count(SchedulerCycle.id))
            .where(SchedulerCycle.id > cycle_id)
        )

    return int(result or 0)


def trading_order_count(
    idempotency_key: str,
) -> int:
    with SessionLocal() as session:
        result = session.scalar(
            select(func.count(TradingOrder.id))
            .where(
                TradingOrder.idempotency_key
                == idempotency_key
            )
        )

    return int(result or 0)


def build_payload(
    idempotency_key: str,
) -> dict[str, Any]:
    return {
        "runtime_risk": {
            "equity": 10000.0,
            "peak_equity": 10000.0,
            "daily_pnl": 0.0,
            "open_positions": 0,
            "current_exposure_value": 0.0,
            "correlated_exposure_value": 0.0,
            "max_daily_loss_percent": 3.0,
            "max_drawdown_percent": 10.0,
            "max_total_exposure_percent": 80.0,
            "max_correlated_exposure_percent": 40.0,
            "max_open_positions": 5,
            "minimum_position_value": 25.0,
        },
        "analysis": {
            "scoring": {
                "score": 90.0,
                "opportunity_score": 90.0,
                "consensus_score": 90.0,
                "confidence": 90,
                "trade_direction": "LONG",
                "signal_score": 90.0,
                "forecast_score": 90.0,
                "news_score": 80.0,
            },
            "market_regime": {
                "market_regime": "BULL",
                "confidence": 90.0,
                "trend_regime": "BULL",
                "risk_environment": "RISK_ON",
                "risk_asset_score": 85.0,
                "defensive_asset_score": 20.0,
                "risk_appetite_score": 85.0,
                "market_breadth_score": 80.0,
                "volatility_score": 35.0,
                "signals": [],
                "reasons": [
                    "Automatic scheduler dry-run verification."
                ],
                "warnings": [],
            },
            "portfolio": {
                "capital": 10000.0,
                "currency": "USDT",
                "risk_level": "medium",
                "max_position_percent": 20.0,
                "max_risk_per_trade_percent": 1.0,
                "portfolio_risk_score": 30.0,
                "cash_reserve_percent": 100.0,
                "invested_percent": 0.0,
                "positions": [
                    {
                        "asset": "BTCUSDT",
                        "target_percent": 10.0,
                        "amount": 1000.0,
                        "action": "ADD",
                        "risk_score": 30.0,
                        "reason": (
                            "Automatic scheduler "
                            "dry-run verification."
                        ),
                    }
                ],
                "trades": [],
                "min_trade_amount": 25.0,
                "trading_fee_percent": 0.1,
                "rebalance_tolerance_percent": 1.0,
                "trade_rounding_amount": 0.01,
                "estimated_total_fees": 0.0,
                "warnings": [],
            },
            "execution": {
                "symbol": "BTCUSDT",
                "current_price": 62000.0,
                "atr": 1000.0,
                "quantity_step": 0.00001,
                "price_tick": 0.01,
                "stop_atr_multiplier": 1.5,
                "take_profit_1_rr": 1.5,
                "take_profit_2_rr": 2.5,
                "minimum_stop_percent": 0.5,
            },
            "account_risk": {
                "equity": 10000.0,
                "peak_equity": 10000.0,
                "daily_pnl": 0.0,
                "open_positions": 0,
                "current_exposure_value": 0.0,
                "correlated_exposure_value": 0.0,
            },
            "risk_limits": {
                "max_daily_loss_percent": 3.0,
                "max_drawdown_percent": 10.0,
                "max_total_exposure_percent": 80.0,
                "max_correlated_exposure_percent": 40.0,
                "max_open_positions": 5,
                "minimum_position_value": 25.0,
            },
            "order_routing": {
                "exchange": "PAPER",
                "market_type": "SPOT",
                "order_type": "MARKET",
                "leverage": 1,
            },
            "idempotency_key": idempotency_key,
            "dry_run": True,
        },
    }


def restore_safe_state(
    original_interval: int,
) -> None:
    try:
        api_request(
            "PATCH",
            "/api/v3/scheduler/state",
            {
                "enabled": False,
                "interval_seconds": original_interval,
            },
        )
    except Exception as exc:
        print(
            "WARNING: scheduler cleanup failed:",
            exc,
        )

    try:
        api_request(
            "DELETE",
            "/api/v3/scheduler/payload",
        )
    except Exception as exc:
        print(
            "WARNING: payload cleanup failed:",
            exc,
        )


def main() -> None:
    print("=== 1. Проверяем исходное состояние ===")

    health = api_request("GET", "/health")
    print("API health:", health)

    initial_state = api_request(
        "GET",
        "/api/v3/scheduler/state",
    )
    initial_payload = api_request(
        "GET",
        "/api/v3/scheduler/payload",
    )
    background = api_request(
        "GET",
        "/api/v3/scheduler/runner/background/status",
    )

    assert initial_state["enabled"] is False, initial_state
    assert initial_state["next_run_at"] is None, initial_state
    assert initial_payload["configured"] is False, initial_payload
    assert background["running"] is True, background
    assert background["failed_ticks"] == 0, background

    original_interval = int(
        initial_state["interval_seconds"]
    )
    baseline_cycle_id = scheduler_cycle_max_id()

    print("Scheduler disabled: OK")
    print("Payload cleared: OK")
    print("Background loop healthy: OK")
    print("Baseline cycle ID:", baseline_cycle_id)

    idempotency_key = (
        "scheduler-v321-auto-"
        f"{uuid4().hex[:16]}"
    )

    assert trading_order_count(idempotency_key) == 0

    test_started = False

    try:
        print()
        print("=== 2. Сохраняем уникальный PAPER payload ===")

        saved_payload = api_request(
            "PUT",
            "/api/v3/scheduler/payload",
            build_payload(idempotency_key),
        )
        test_started = True

        assert saved_payload["configured"] is True
        assert (
            saved_payload["analysis_payload"]["dry_run"]
            is True
        )
        assert (
            saved_payload["analysis_payload"]
            ["order_routing"]["exchange"]
            == "PAPER"
        )
        assert (
            saved_payload["analysis_payload"]
            ["idempotency_key"]
            == idempotency_key
        )

        print("Payload configured: OK")
        print("Idempotency key:", idempotency_key)

        print()
        print("=== 3. Включаем scheduler на 60 секунд ===")

        enabled_state = api_request(
            "PATCH",
            "/api/v3/scheduler/state",
            {
                "enabled": True,
                "interval_seconds": (
                    TEST_INTERVAL_SECONDS
                ),
            },
        )

        assert enabled_state["enabled"] is True
        assert (
            enabled_state["interval_seconds"]
            == TEST_INTERVAL_SECONDS
        )
        assert enabled_state["next_run_at"] is not None

        due_at = parse_datetime(
            enabled_state["next_run_at"]
        )

        print(
            "Next run at:",
            due_at.isoformat(),
        )

        print()
        print(
            "=== 4. Ожидаем автоматический cycle ==="
        )

        deadline = (
            time.monotonic()
            + EXECUTION_TIMEOUT_SECONDS
        )
        observed_cycle_id: int | None = None

        while time.monotonic() < deadline:
            state = api_request(
                "GET",
                "/api/v3/scheduler/state",
            )

            current_cycle_id = int(
                state["last_cycle_id"] or 0
            )

            if current_cycle_id > baseline_cycle_id:
                observed_cycle_id = current_cycle_id
                break

            remaining = max(
                0,
                int(
                    (
                        due_at
                        - datetime.now(timezone.utc)
                    ).total_seconds()
                ),
            )

            print(
                "Waiting; seconds until due:",
                remaining,
                end="\r",
                flush=True,
            )
            time.sleep(1)

        print()

        if observed_cycle_id is None:
            raise TimeoutError(
                "Automatic scheduler cycle did not "
                "execute before timeout."
            )

        disabled_state = api_request(
            "PATCH",
            "/api/v3/scheduler/state",
            {"enabled": False},
        )

        assert disabled_state["enabled"] is False
        assert disabled_state["next_run_at"] is None

        print(
            "Automatic cycle ID:",
            observed_cycle_id,
        )
        print("Scheduler disabled immediately: OK")

        print()
        print("=== 5. Проверяем scheduler cycle ===")

        cycle = api_request(
            "GET",
            (
                "/api/v3/scheduler/cycles/"
                f"{observed_cycle_id}"
            ),
        )

        assert cycle["status"] == "COMPLETED", cycle
        assert cycle["dry_run"] is True, cycle
        assert cycle["error_message"] is None, cycle
        assert cycle["risk"]["status"] == "ALLOW", cycle

        cycle_started_at = parse_datetime(
            cycle["started_at"]
        )
        assert cycle_started_at >= due_at, {
            "due_at": due_at.isoformat(),
            "started_at": (
                cycle_started_at.isoformat()
            ),
        }

        execution = cycle["execution"]
        assert execution["action"] == "DRY_RUN", execution
        assert execution["reason"] is None, execution

        journal = execution["journal"]

        assert (
            journal["idempotency_key"]
            == idempotency_key
        ), journal
        assert journal["replayed"] is False, journal
        assert journal["dry_run"] is True, journal
        assert journal["exchange"] == "PAPER", journal
        assert journal["market_type"] == "SPOT", journal
        assert journal["symbol"] == "BTCUSDT", journal
        assert journal["status"] == "DRY_RUN", journal
        assert journal["simulated"] is True, journal
        assert journal["client_order_id"] is None, journal
        assert journal["exchange_order_id"] is None, journal
        assert float(journal["filled_quantity"]) == 0.0

        print("Cycle status COMPLETED: OK")
        print("Runtime risk ALLOW: OK")
        print("Trading action DRY_RUN: OK")
        print("PAPER simulated order: OK")
        print("No exchange order created: OK")
        print(
            "Started after next_run_at: OK"
        )

        print()
        print("=== 6. Проверяем отсутствие дублей ===")

        new_cycle_count = scheduler_cycle_count_after(
            baseline_cycle_id
        )
        order_count = trading_order_count(
            idempotency_key
        )

        assert new_cycle_count == 1, new_cycle_count
        assert order_count == 1, order_count

        print("New scheduler cycles: 1")
        print("Trading orders for key: 1")

        print()
        print(
            "=== 7. Проверяем стабильность "
            "после отключения ==="
        )

        time.sleep(10)

        assert (
            scheduler_cycle_count_after(
                baseline_cycle_id
            )
            == 1
        )
        assert (
            trading_order_count(
                idempotency_key
            )
            == 1
        )

        final_background = api_request(
            "GET",
            (
                "/api/v3/scheduler/"
                "runner/background/status"
            ),
        )

        assert final_background["running"] is True
        assert final_background["failed_ticks"] == 0
        assert final_background["last_error"] is None

        print("No duplicate cycle: OK")
        print("No duplicate order: OK")
        print("Background loop healthy: OK")

    finally:
        if test_started:
            restore_safe_state(original_interval)

    print()
    print("=== 8. Проверяем финальную безопасность ===")

    final_state = api_request(
        "GET",
        "/api/v3/scheduler/state",
    )
    final_payload = api_request(
        "GET",
        "/api/v3/scheduler/payload",
    )

    assert final_state["enabled"] is False
    assert final_state["next_run_at"] is None
    assert (
        final_state["interval_seconds"]
        == original_interval
    )
    assert final_payload["configured"] is False
    assert (
        final_payload["runtime_risk_payload"]
        is None
    )
    assert final_payload["analysis_payload"] is None

    print("Scheduler disabled: OK")
    print("Original interval restored: OK")
    print("Payload cleared: OK")

    print()
    print("=== v3.21 verification passed ===")
    print("Cycle ID:", observed_cycle_id)
    print("Idempotency key:", idempotency_key)


if __name__ == "__main__":
    main()
