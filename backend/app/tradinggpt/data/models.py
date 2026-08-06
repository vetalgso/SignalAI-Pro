from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MarketDataWarning(BaseModel):
    code: str
    message: str


class MarketSnapshot(BaseModel):
    """Normalized market snapshot shared by TradingGPT modules."""

    asset: str
    symbol: str
    interval: str
    candle_limit: int

    price: float
    candles: list[dict[str, Any]]
    indicators: dict[str, Any]

    volume_ratio: float | None = None

    source: str = "binance"
    fetched_at: datetime
    age_seconds: float = Field(default=0.0, ge=0)
    from_cache: bool = False

    data_quality: int = Field(ge=0, le=100)
    warnings: list[MarketDataWarning] = Field(default_factory=list)
