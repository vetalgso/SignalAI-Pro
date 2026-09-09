from __future__ import annotations

from app.tradinggpt.market_regime.models import (
    MarketRegimeResult,
)
from app.tradinggpt.pipeline import (
    TradingPipeline,
    TradingPipelineResult,
)
from app.tradinggpt.portfolio.models import PortfolioResult
from app.tradinggpt.scoring.models import ScoringResult


def build_scoring_result() -> ScoringResult:
    return ScoringResult(
        score=82.0,
        opportunity_score=85.0,
        consensus_score=70.0,
        confidence=90,
        trade_direction="LONG",
        signal_score=80.0,
        forecast_score=84.0,
        news_score=76.0,
    )


def build_market_regime_result() -> MarketRegimeResult:
    return MarketRegimeResult(
        market_regime="RISK_ON",
        confidence=0.88,
        trend_regime="BULL",
        risk_environment="RISK_ON",
        risk_asset_score=78.0,
        defensive_asset_score=22.0,
        risk_appetite_score=75.0,
        market_breadth_score=0.72,
        volatility_score=35.0,
        signals=(),
        reasons=(
            "Risk assets are broadly supported.",
        ),
        warnings=(),
    )


def build_portfolio_result() -> PortfolioResult:
    return PortfolioResult(
        capital=10_000.0,
        currency="USD",
        risk_level="medium",
        max_position_percent=25.0,
        max_risk_per_trade_percent=1.0,
        portfolio_risk_score=30.0,
        cash_reserve_percent=20.0,
        invested_percent=80.0,
        positions=[],
        trades=[],
        min_trade_amount=25.0,
        trading_fee_percent=0.1,
        rebalance_tolerance_percent=0.5,
        trade_rounding_amount=1.0,
        estimated_total_fees=0.0,
        warnings=[],
    )


def verify_pipeline_result() -> TradingPipelineResult:
    scoring_result = build_scoring_result()
    market_result = build_market_regime_result()
    portfolio_result = build_portfolio_result()

    result = TradingPipeline.run(
        scoring_result=scoring_result,
        market_regime_result=market_result,
        portfolio_result=portfolio_result,
    )

    assert isinstance(result, TradingPipelineResult)

    assert result.scoring is scoring_result
    assert result.market_regime is market_result
    assert result.portfolio is portfolio_result

    assert result.conviction.score == 76.5
    assert result.conviction.level == "HIGH"
    assert result.conviction.recommendation == "BUY"
    assert result.conviction.confidence == 0.765
    assert result.conviction.position_multiplier == 1.25

    print("TradingGPT pipeline result verification passed")

    return result


def verify_pipeline_serialization(
    result: TradingPipelineResult,
) -> None:
    payload = result.to_dict()

    assert set(payload) == {
        "scoring",
        "market_regime",
        "portfolio",
        "conviction",
    }

    scoring = payload["scoring"]
    conviction = payload["conviction"]

    assert isinstance(scoring, dict)
    assert isinstance(conviction, dict)

    assert scoring["trade_direction"] == "LONG"
    assert conviction["score"] == 76.5
    assert conviction["level"] == "HIGH"
    assert conviction["recommendation"] == "BUY"

    factors = conviction["factors"]

    assert isinstance(factors, dict)
    assert factors == {
        "signal_score": 80.0,
        "market_score": 75.0,
        "portfolio_score": 70.0,
        "quality_score": 80.0,
    }

    print(
        "TradingGPT pipeline serialization verification passed"
    )


def main() -> None:
    result = verify_pipeline_result()
    verify_pipeline_serialization(result)

    print("TradingGPT Pipeline verification passed")


if __name__ == "__main__":
    main()
