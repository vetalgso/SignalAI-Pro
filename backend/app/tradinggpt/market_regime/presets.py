from __future__ import annotations

from app.tradinggpt.market_regime.models import AssetRole


ASSET_ALIASES: dict[str, str] = {
    "BITCOIN": "BTC",
    "BTCUSDT": "BTC",
    "BTC/USD": "BTC",
    "ETHEREUM": "ETH",
    "ETHUSDT": "ETH",
    "ETH/USD": "ETH",
    "NASDAQ 100": "NASDAQ",
    "NASDAQ ETF": "NASDAQ",
    "QQQ": "NASDAQ",
    "S&P 500": "SP500",
    "S&P500": "SP500",
    "S&P 500 ETF": "SP500",
    "SPY": "SP500",
    "XAU": "GOLD",
    "XAUUSD": "GOLD",
    "CASH": "CASH",
    "USD": "CASH",
    "CASH / USD": "CASH",
}


ASSET_ROLES: dict[str, AssetRole] = {
    "BTC": "risk",
    "ETH": "risk",
    "NASDAQ": "risk",
    "SP500": "risk",
    "GROWTH STOCKS": "risk",
    "GOLD": "defensive",
    "CASH": "defensive",
    "DXY": "defensive",
}


ASSET_WEIGHTS: dict[str, float] = {
    "BTC": 1.20,
    "ETH": 1.00,
    "NASDAQ": 1.10,
    "SP500": 1.00,
    "GROWTH STOCKS": 0.80,
    "GOLD": 0.90,
    "CASH": 0.70,
    "DXY": 0.80,
}


def normalize_asset(asset: str) -> str:
    normalized = " ".join(
        asset.strip().upper().split()
    )

    return ASSET_ALIASES.get(
        normalized,
        normalized,
    )


def asset_role(asset: str) -> AssetRole:
    normalized = normalize_asset(asset)

    return ASSET_ROLES.get(
        normalized,
        "neutral",
    )


def asset_weight(asset: str) -> float:
    normalized = normalize_asset(asset)

    return ASSET_WEIGHTS.get(
        normalized,
        0.50,
    )
