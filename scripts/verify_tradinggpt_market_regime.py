from __future__ import annotations

from app.tradinggpt.market_regime import (
    MarketObservation,
    MarketRegimeEngine,
)
from app.tradinggpt.portfolio import PortfolioEngine


def allocation(result) -> dict[str, float]:
    return {
        position.asset: position.target_percent
        for position in result.positions
    }


def verify_market_regime() -> None:
    engine = MarketRegimeEngine()

    result = engine.analyze(
        (
            MarketObservation(
                asset="BTC",
                trend_score=80,
                momentum_score=70,
                volatility_score=55,
            ),
            MarketObservation(
                asset="ETH",
                trend_score=70,
                momentum_score=65,
                volatility_score=60,
            ),
            MarketObservation(
                asset="NASDAQ",
                trend_score=55,
                momentum_score=50,
                volatility_score=45,
            ),
            MarketObservation(
                asset="Gold",
                trend_score=-25,
                momentum_score=-20,
                volatility_score=25,
            ),
        )
    )

    assert result.market_regime == "RISK_ON"
    assert result.risk_environment == "RISK_ON"
    assert result.trend_regime == "BULL"
    assert result.risk_asset_score > 0
    assert result.risk_appetite_score > 0
    assert 0 <= result.confidence <= 1
    assert len(result.signals) == 4

    print("Market Regime verification passed")


def verify_dynamic_portfolio() -> None:
    result = PortfolioEngine.build(
        risk_level="medium",
        capital=10_000,
        market_regime="RISK_ON",
    )

    positions = allocation(result)

    assert round(sum(positions.values()), 2) == 100.0
    assert positions["BTC"] == 25.0
    assert positions["ETH"] == 25.0
    assert positions["NASDAQ ETF"] == 20.0
    assert positions["Growth Stocks"] == 10.0
    assert positions["Gold"] == 5.0
    assert positions["Cash / USD"] == 15.0
    assert any(
        "RISK_ON" in warning
        for warning in result.warnings
    )

    print("Dynamic Portfolio verification passed")


def verify_risk_off_portfolio() -> None:
    result = PortfolioEngine.build(
        risk_level="medium",
        capital=10_000,
        market_regime="RISK_OFF",
    )

    positions = allocation(result)

    assert round(sum(positions.values()), 2) == 100.0
    assert positions["Cash / USD"] == 40.0
    assert positions["Gold"] == 25.0
    assert positions["S&P 500 ETF"] == 15.0
    assert positions["NASDAQ ETF"] == 10.0
    assert positions["BTC"] == 5.0
    assert positions["ETH"] == 5.0

    print("Risk-Off Portfolio verification passed")


def verify_legacy_compatibility() -> None:
    result = PortfolioEngine.build(
        risk_level="medium",
        capital=10_000,
    )

    positions = allocation(result)

    assert round(sum(positions.values()), 2) == 100.0
    assert positions["BTC"] == 25.0
    assert positions["ETH"] == 20.0
    assert positions["NASDAQ ETF"] == 20.0
    assert positions["Gold"] == 15.0
    assert positions["S&P 500 ETF"] == 10.0
    assert positions["Cash / USD"] == 10.0
    assert not any(
        "рыночный режим" in warning.lower()
        for warning in result.warnings
    )

    print("Legacy compatibility verification passed")


if __name__ == "__main__":
    verify_market_regime()
    verify_dynamic_portfolio()
    verify_risk_off_portfolio()
    verify_legacy_compatibility()

    print("TradingGPT Market Intelligence verification passed")
