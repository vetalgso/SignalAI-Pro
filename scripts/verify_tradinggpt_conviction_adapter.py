from __future__ import annotations

from app.tradinggpt.conviction import (
    ConvictionAdapter,
    ConvictionEngine,
)
from app.tradinggpt.market_regime.models import (
    MarketRegimeResult,
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
        reasons=("Risk assets are broadly supported.",),
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


def verify_factor_mapping() -> None:
    factors = ConvictionAdapter.from_results(
        scoring_result=build_scoring_result(),
        market_regime_result=build_market_regime_result(),
        portfolio_result=build_portfolio_result(),
    )

    assert factors.signal_score == 80.0
    assert factors.market_score == 75.0
    assert factors.portfolio_score == 70.0
    assert factors.quality_score == 80.0

    print("Conviction factor mapping verification passed")


def verify_conviction_pipeline() -> None:
    factors = ConvictionAdapter.from_results(
        scoring_result=build_scoring_result(),
        market_regime_result=build_market_regime_result(),
        portfolio_result=build_portfolio_result(),
    )

    result = ConvictionEngine.calculate(
        factors=factors,
    )

    # 80 * 0.35 = 28.0
    # 75 * 0.30 = 22.5
    # 70 * 0.20 = 14.0
    # 80 * 0.15 = 12.0
    # total = 76.5
    assert result.score == 76.5
    assert result.level == "HIGH"
    assert result.recommendation == "BUY"
    assert result.confidence == 0.765
    assert result.position_multiplier == 1.25

    print("Conviction integrated pipeline verification passed")


def verify_score_clamping() -> None:
    scoring_result = ScoringResult(
        score=50.0,
        opportunity_score=50.0,
        consensus_score=150.0,
        confidence=150,
        trade_direction="NEUTRAL",
        signal_score=125.0,
        forecast_score=50.0,
        news_score=50.0,
    )

    market_result = MarketRegimeResult(
        market_regime="SIDEWAYS",
        confidence=0.5,
        trend_regime="SIDEWAYS",
        risk_environment="NEUTRAL",
        risk_asset_score=0.0,
        defensive_asset_score=0.0,
        risk_appetite_score=-25.0,
        market_breadth_score=0.0,
        volatility_score=50.0,
        signals=(),
    )

    portfolio_result = build_portfolio_result()

    factors = ConvictionAdapter.from_results(
        scoring_result=scoring_result,
        market_regime_result=market_result,
        portfolio_result=portfolio_result,
    )

    assert factors.signal_score == 100.0
    assert factors.market_score == 0.0
    assert factors.portfolio_score == 70.0
    assert factors.quality_score == 100.0

    print("Conviction adapter clamping verification passed")


def main() -> None:
    verify_factor_mapping()
    verify_conviction_pipeline()
    verify_score_clamping()

    print("TradingGPT Conviction Adapter verification passed")


if __name__ == "__main__":
    main()
