from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MarketDataProvider(ABC):
    """Contract for external market-data providers."""

    name: str

    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        interval: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def get_candle_history(
        self, symbol: str, interval: str, limit: int, *,
        start_time: int, end_time: int,
    ) -> list[dict[str, Any]]:
        """Fetch a bounded historical page; latest-only providers must fail closed."""
        raise NotImplementedError("Provider does not support historical ranges")
