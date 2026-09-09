from __future__ import annotations

from app.tradinggpt.engine import TradingGPTEngine
from app.tradinggpt.engine.schemas import TradingGPTAnalyzeRequest


def test_engine_builds_expected_conviction(
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

    conviction = result.to_dict()["conviction"]

    assert conviction["score"] == 76.5
    assert conviction["level"] == "HIGH"
    assert conviction["recommendation"] == "BUY"
    assert conviction["confidence"] == 0.765
    assert conviction["position_multiplier"] == 1.25

    assert conviction["factors"] == {
        "signal_score": 80.0,
        "market_score": 75.0,
        "portfolio_score": 70.0,
        "quality_score": 80.0,
    }


def test_engine_returns_explanation(
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

    explanation = result.to_dict()["explanation"]

    assert explanation["risk_level"] == "MEDIUM"
    assert "BUY setup" in explanation["summary"]
    assert "HIGH conviction" in explanation["summary"]
    assert explanation["pros"]
    assert explanation["cons"]
    assert explanation["risks"]
