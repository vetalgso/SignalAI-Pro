from __future__ import annotations

from app.tradinggpt.market_regime.models import MarketRegime


REGIME_ALLOCATIONS: dict[MarketRegime, dict[str, float]] = {
    "RISK_ON": {
        "BTC": 35.0,
        "ETH": 25.0,
        "NASDAQ ETF": 20.0,
        "Growth Stocks": 10.0,
        "Gold": 5.0,
        "Cash / USD": 5.0,
    },
    "RISK_OFF": {
        "Cash / USD": 35.0,
        "Gold": 30.0,
        "S&P 500 ETF": 15.0,
        "NASDAQ ETF": 10.0,
        "BTC": 5.0,
        "ETH": 5.0,
    },
    "BULL": {
        "BTC": 30.0,
        "ETH": 20.0,
        "NASDAQ ETF": 25.0,
        "S&P 500 ETF": 15.0,
        "Gold": 5.0,
        "Cash / USD": 5.0,
    },
    "BEAR": {
        "Cash / USD": 30.0,
        "Gold": 30.0,
        "S&P 500 ETF": 20.0,
        "NASDAQ ETF": 10.0,
        "BTC": 5.0,
        "ETH": 5.0,
    },
    "SIDEWAYS": {
        "BTC": 20.0,
        "ETH": 15.0,
        "NASDAQ ETF": 20.0,
        "S&P 500 ETF": 20.0,
        "Gold": 15.0,
        "Cash / USD": 10.0,
    },
    "HIGH_VOLATILITY": {
        "Cash / USD": 35.0,
        "Gold": 25.0,
        "S&P 500 ETF": 20.0,
        "NASDAQ ETF": 10.0,
        "BTC": 5.0,
        "ETH": 5.0,
    },
}


def allocation_for_regime(
    regime: MarketRegime,
) -> dict[str, float]:
    return dict(REGIME_ALLOCATIONS[regime])
