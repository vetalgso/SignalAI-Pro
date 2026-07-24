from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, Field


ALLOWED_KLINE_INTERVALS = {
    "1s", "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
}


class MarketStatus(BaseModel):
    exchange: str = "Binance"
    connected: bool
    market_data_url: str
    authentication_required: bool = False


class TradingPair(BaseModel):
    symbol: str
    base_asset: str
    quote_asset: str
    status: str


class TradingPairsResponse(BaseModel):
    count: int
    quote_assets: list[str]
    pairs: list[TradingPair]


class TickerPrice(BaseModel):
    symbol: str
    price: Decimal
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Kline(BaseModel):
    open_time: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    close_time: int
    quote_asset_volume: Decimal
    trade_count: int
    taker_buy_base_volume: Decimal
    taker_buy_quote_volume: Decimal


class KlineResponse(BaseModel):
    symbol: str
    interval: str
    limit: int
    candles: list[Kline]
