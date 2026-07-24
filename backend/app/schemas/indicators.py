from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class MovingAverages(BaseModel):
    ema20: float | None
    ema50: float | None
    ema200: float | None
    sma20: float | None
    sma50: float | None


class MacdValues(BaseModel):
    macd: float
    signal: float
    histogram: float


class BollingerValues(BaseModel):
    upper: float
    middle: float
    lower: float
    width_percent: float


class VolumeValues(BaseModel):
    current: Decimal
    average20: float | None
    ratio: float | None


class MarketState(BaseModel):
    trend: Literal["bullish", "bearish", "neutral"]
    momentum: Literal["bullish", "bearish", "neutral", "overbought", "oversold"]
    volatility: Literal["low", "normal", "high"]
    trend_strength: Literal["weak", "strong", "unknown"]


class IndicatorResponse(BaseModel):
    symbol: str
    interval: str
    candles_used: int
    price: Decimal
    candle_open_time: int
    candle_close_time: int
    moving_averages: MovingAverages
    rsi14: float | None
    macd: MacdValues | None
    bollinger: BollingerValues | None
    atr14: float | None
    atr_percent: float | None
    adx14: float | None
    volume: VolumeValues
    market_state: MarketState
