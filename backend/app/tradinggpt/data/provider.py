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
