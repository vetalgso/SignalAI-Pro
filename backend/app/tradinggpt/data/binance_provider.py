from __future__ import annotations

from typing import Any

from app.services.binance_market import BinanceMarketService
from app.tradinggpt.data.provider import MarketDataProvider


class BinanceMarketDataProvider(MarketDataProvider):
    name = "binance"

    def __init__(self, service: BinanceMarketService | None = None) -> None:
        self._service = service or BinanceMarketService()

    async def get_candles(
        self,
        symbol: str,
        interval: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        return await self._service.klines(symbol, interval, limit)
