from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.binance_market import BinanceMarketService


FALLBACK_ASSETS = [
    "BTC",
    "ETH",
    "BNB",
    "SOL",
    "XRP",
    "DOGE",
    "ADA",
    "TRX",
    "AVAX",
    "LINK",
    "SUI",
    "TON",
    "DOT",
    "LTC",
    "BCH",
    "NEAR",
    "APT",
    "UNI",
    "AAVE",
    "ATOM",
]

EXCLUDED_BASE_ASSETS = {
    "USDT",
    "USDC",
    "FDUSD",
    "TUSD",
    "USDP",
    "DAI",
    "EUR",
    "AEUR",
}

LEVERAGED_SUFFIXES = (
    "UP",
    "DOWN",
    "BULL",
    "BEAR",
)


@dataclass(slots=True)
class MarketUniverseSelection:
    assets: list[str]
    source: str
    warnings: list[str] = field(default_factory=list)


class BinanceLiquidMarketUniverse:
    """Select liquid Binance Spot USDT markets using public 24h turnover."""

    def __init__(
        self,
        service: BinanceMarketService | None = None,
    ) -> None:
        self.service = service or BinanceMarketService()

    async def select(
        self,
        *,
        limit: int,
    ) -> MarketUniverseSelection:
        bounded_limit = max(1, min(int(limit), 100))

        try:
            pairs = await self.service.trading_pairs()
            tickers = await self.service.ticker_24h()
            assets = self._rank_assets(
                pairs=pairs,
                tickers=tickers,
                limit=bounded_limit,
            )
        except Exception as exc:
            return MarketUniverseSelection(
                assets=FALLBACK_ASSETS[:bounded_limit],
                source="STATIC_FALLBACK",
                warnings=[
                    "DYNAMIC_UNIVERSE_FAILED:"
                    f"{type(exc).__name__}"
                ],
            )

        if not assets:
            return MarketUniverseSelection(
                assets=FALLBACK_ASSETS[:bounded_limit],
                source="STATIC_FALLBACK",
                warnings=["DYNAMIC_UNIVERSE_EMPTY"],
            )

        return MarketUniverseSelection(
            assets=assets,
            source="BINANCE_24H_QUOTE_VOLUME",
        )

    @classmethod
    def _rank_assets(
        cls,
        *,
        pairs: list[dict[str, str]],
        tickers: list[dict[str, Any]],
        limit: int,
    ) -> list[str]:
        eligible = {
            pair["symbol"]: pair["base_asset"]
            for pair in pairs
            if pair.get("quote_asset") == "USDT"
            and cls._is_eligible_asset(pair.get("base_asset", ""))
        }

        ranked: list[tuple[Decimal, str]] = []

        for ticker in tickers:
            symbol = ticker.get("symbol")
            asset = eligible.get(str(symbol))

            if asset is None:
                continue

            try:
                quote_volume = Decimal(str(ticker.get("quoteVolume", "0")))
            except (InvalidOperation, TypeError, ValueError):
                continue

            if quote_volume > 0:
                ranked.append((quote_volume, asset))

        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [asset for _, asset in ranked[:limit]]

    @staticmethod
    def _is_eligible_asset(asset: str) -> bool:
        normalized = asset.strip().upper()

        return (
            bool(normalized)
            and normalized not in EXCLUDED_BASE_ASSETS
            and not any(
                normalized.endswith(suffix)
                for suffix in LEVERAGED_SUFFIXES
            )
        )
