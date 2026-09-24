from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.tradinggpt.engine import TradingGPTEngine
from app.tradinggpt.engine.schemas import TradingGPTAnalyzeRequest
from app.tradinggpt.execution import MarketExecutionContext
from app.tradinggpt.risk import AccountRiskContext


def test_engine_returns_execute_decision(
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
            daily_pnl=0.0,
            open_positions=1,
            current_exposure_value=2_000.0,
            correlated_exposure_value=500.0,
        ),
    )

    assert result.decision is not None
    assert result.decision.status == "EXECUTE"
    assert result.decision.executable is True
    assert result.decision.symbol == "BTCUSDT"
    assert result.decision.approved_quantity == 0.025
    assert result.decision.approved_value == 2_500.0
    assert result.decision.approved_risk == 37.5


def test_engine_returns_no_trade_without_execution_context(
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
    )

    assert result.execution_plan is None
    assert result.risk_decision is None
    assert result.decision is not None
    assert result.decision.status == "NO_TRADE"
    assert result.decision.executable is False


def test_engine_returns_no_trade_without_risk_context(
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
    assert result.decision is not None
    assert result.decision.status == "NO_TRADE"
    assert result.decision.execution_ready is True
    assert result.decision.risk_allowed is False


def test_endpoint_returns_execute_decision(
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

    decision = response.json()["decision"]

    assert decision["status"] == "EXECUTE"
    assert decision["executable"] is True
    assert decision["symbol"] == "BTCUSDT"
    assert decision["recommendation"] == "BUY"
    assert decision["approved_quantity"] == 0.025
    assert decision["approved_value"] == 2_500.0
    assert decision["approved_risk"] == 37.5


def test_endpoint_returns_reduced_decision(
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

    decision = response.json()["decision"]

    assert decision["status"] == "EXECUTE_REDUCED"
    assert decision["executable"] is True
    assert decision["approved_quantity"] == 0.01
    assert decision["approved_value"] == 1_000.0
    assert decision["approved_risk"] == 15.0


def test_endpoint_returns_reject_decision(
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

    decision = response.json()["decision"]

    assert decision["status"] == "REJECT"
    assert decision["executable"] is False
    assert decision["risk_allowed"] is False
    assert decision["approved_quantity"] == 0.0
    assert decision["approved_value"] == 0.0
    assert decision["approved_risk"] == 0.0


def test_endpoint_returns_no_trade_without_optional_context(
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
    assert payload["decision"]["status"] == "NO_TRADE"
    assert payload["decision"]["executable"] is False
