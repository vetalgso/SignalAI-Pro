from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.tradinggpt.engine import TradingGPTEngine
from app.tradinggpt.engine.schemas import TradingGPTAnalyzeRequest
from app.tradinggpt.execution import MarketExecutionContext
from app.tradinggpt.risk import AccountRiskContext


def test_engine_returns_risk_decision(
    analyze_request: TradingGPTAnalyzeRequest,
) -> None:
    result = TradingGPTEngine.analyze(
        scoring_result=analyze_request.scoring.to_domain(),
        market_regime_result=(
            analyze_request.market_regime.to_domain()
        ),
        portfolio_result=(
            analyze_request.portfolio.to_domain()
        ),
        execution_context=MarketExecutionContext(
            symbol="BTCUSDT",
            current_price=100_000.0,
            atr=1_000.0,
            quantity_step=0.000001,
            price_tick=0.1,
        ),
        account_risk_context=AccountRiskContext(
            equity=10_000.0,
            peak_equity=10_000.0,
            daily_pnl=-50.0,
            open_positions=1,
            current_exposure_value=2_000.0,
            correlated_exposure_value=500.0,
        ),
    )

    assert result.execution_plan is not None
    assert result.risk_decision is not None
    assert result.risk_decision.status == "ALLOW"
    assert result.risk_decision.approved_position_value == 2_500.0
    assert result.risk_decision.approved_position_quantity == 0.025


def test_engine_returns_no_risk_decision_without_account_context(
    analyze_request: TradingGPTAnalyzeRequest,
) -> None:
    result = TradingGPTEngine.analyze(
        scoring_result=analyze_request.scoring.to_domain(),
        market_regime_result=(
            analyze_request.market_regime.to_domain()
        ),
        portfolio_result=(
            analyze_request.portfolio.to_domain()
        ),
        execution_context=MarketExecutionContext(
            symbol="BTCUSDT",
            current_price=100_000.0,
            atr=1_000.0,
        ),
    )

    assert result.execution_plan is not None
    assert result.risk_decision is None


def test_analysis_endpoint_returns_allow_decision(
    client: TestClient,
    analysis_payload: dict[str, Any],
) -> None:
    request_payload = {
        **analysis_payload,
        "execution": {
            "symbol": "BTCUSDT",
            "current_price": 100_000.0,
            "atr": 1_000.0,
            "quantity_step": 0.000001,
            "price_tick": 0.1,
        },
        "account_risk": {
            "equity": 10_000.0,
            "peak_equity": 10_000.0,
            "daily_pnl": -50.0,
            "open_positions": 1,
            "current_exposure_value": 2_000.0,
            "correlated_exposure_value": 500.0,
        },
    }

    response = client.post(
        "/api/v3/engine/analyze",
        json=request_payload,
    )

    assert response.status_code == 200

    payload = response.json()
    decision = payload["risk_decision"]

    assert payload["execution_plan"]["status"] == "READY"
    assert decision["status"] == "ALLOW"
    assert decision["allowed"] is True
    assert decision["approved_position_value"] == 2_500.0
    assert decision["approved_position_quantity"] == 0.025


def test_analysis_endpoint_reduces_position(
    client: TestClient,
    analysis_payload: dict[str, Any],
) -> None:
    request_payload = {
        **analysis_payload,
        "execution": {
            "symbol": "BTCUSDT",
            "current_price": 100_000.0,
            "atr": 1_000.0,
            "quantity_step": 0.000001,
            "price_tick": 0.1,
        },
        "account_risk": {
            "equity": 10_000.0,
            "peak_equity": 10_000.0,
            "daily_pnl": 0.0,
            "open_positions": 2,
            "current_exposure_value": 7_000.0,
            "correlated_exposure_value": 1_000.0,
        },
        "risk_limits": {
            "max_daily_loss_percent": 3.0,
            "max_drawdown_percent": 10.0,
            "max_total_exposure_percent": 80.0,
            "max_correlated_exposure_percent": 50.0,
            "max_open_positions": 5,
            "minimum_position_value": 25.0,
        },
    }

    response = client.post(
        "/api/v3/engine/analyze",
        json=request_payload,
    )

    assert response.status_code == 200

    decision = response.json()["risk_decision"]

    assert decision["status"] == "REDUCE_SIZE"
    assert decision["approved_position_value"] == 1_000.0
    assert decision["approved_position_quantity"] == 0.01
    assert decision["size_multiplier"] == 0.4


def test_analysis_endpoint_denies_trade_after_daily_loss(
    client: TestClient,
    analysis_payload: dict[str, Any],
) -> None:
    request_payload = {
        **analysis_payload,
        "execution": {
            "symbol": "BTCUSDT",
            "current_price": 100_000.0,
            "atr": 1_000.0,
        },
        "account_risk": {
            "equity": 10_000.0,
            "peak_equity": 10_000.0,
            "daily_pnl": -300.0,
            "open_positions": 1,
            "current_exposure_value": 2_000.0,
        },
    }

    response = client.post(
        "/api/v3/engine/analyze",
        json=request_payload,
    )

    assert response.status_code == 200

    decision = response.json()["risk_decision"]

    assert decision["status"] == "DENY"
    assert decision["allowed"] is False
    assert decision["approved_position_value"] == 0.0
    assert (
        "Maximum daily loss limit has been reached."
        in decision["reasons"]
    )


def test_analysis_endpoint_remains_backward_compatible(
    client: TestClient,
    analysis_payload: dict[str, Any],
) -> None:
    response = client.post(
        "/api/v3/engine/analyze",
        json=analysis_payload,
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["execution_plan"] is None
    assert payload["risk_decision"] is None


def test_account_risk_schema_rejects_invalid_equity(
    client: TestClient,
    analysis_payload: dict[str, Any],
) -> None:
    request_payload = {
        **analysis_payload,
        "account_risk": {
            "equity": 0,
            "peak_equity": 10_000.0,
            "daily_pnl": 0.0,
            "open_positions": 0,
            "current_exposure_value": 0.0,
        },
    }

    response = client.post(
        "/api/v3/engine/analyze",
        json=request_payload,
    )

    assert response.status_code == 422
