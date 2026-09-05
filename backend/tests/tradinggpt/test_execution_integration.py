from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.tradinggpt.engine import TradingGPTEngine
from app.tradinggpt.engine.schemas import (
    TradingGPTAnalyzeRequest,
)
from app.tradinggpt.execution import (
    MarketExecutionContext,
)


def test_engine_returns_execution_plan(
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
    )

    payload = result.to_dict()
    plan = payload["execution_plan"]

    assert plan is not None
    assert plan["status"] == "READY"
    assert plan["symbol"] == "BTCUSDT"
    assert plan["side"] == "LONG"
    assert plan["entry_price"] == 100_000.0
    assert plan["stop_loss"] == 98_500.0
    assert plan["take_profit_1"] == 102_250.0
    assert plan["take_profit_2"] == 103_750.0
    assert plan["position_quantity"] == 0.025
    assert plan["position_value"] == 2_500.0
    assert plan["actual_risk_amount"] == 37.5


def test_engine_remains_backward_compatible(
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

    assert result.to_dict()["execution_plan"] is None


def test_analysis_endpoint_returns_execution_plan(
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
    }

    response = client.post(
        "/api/v3/engine/analyze",
        json=request_payload,
    )

    assert response.status_code == 200

    payload = response.json()
    plan = payload["execution_plan"]

    assert plan["status"] == "READY"
    assert plan["recommendation"] == "BUY"
    assert plan["entry_price"] == 100_000.0
    assert plan["stop_loss"] == 98_500.0
    assert plan["position_quantity"] == 0.025
    assert plan["position_cap_applied"] is True


def test_analysis_endpoint_accepts_request_without_execution(
    client: TestClient,
    analysis_payload: dict[str, Any],
) -> None:
    response = client.post(
        "/api/v3/engine/analyze",
        json=analysis_payload,
    )

    assert response.status_code == 200
    assert response.json()["execution_plan"] is None


def test_execution_schema_rejects_invalid_price(
    client: TestClient,
    analysis_payload: dict[str, Any],
) -> None:
    request_payload = {
        **analysis_payload,
        "execution": {
            "symbol": "BTCUSDT",
            "current_price": 0,
            "atr": 1_000.0,
        },
    }

    response = client.post(
        "/api/v3/engine/analyze",
        json=request_payload,
    )

    assert response.status_code == 422
