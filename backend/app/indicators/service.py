from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.indicators.calculations import adx, atr, bollinger_bands, ema, macd, rsi, sma


def _rounded(value: float | None, digits: int = 8) -> float | None:
    return None if value is None else round(value, digits)


def calculate_indicator_snapshot(candles: list[dict[str, Any]]) -> dict[str, Any]:
    if not candles:
        raise ValueError("At least one candle is required")

    closes = [float(candle["close"]) for candle in candles]
    highs = [float(candle["high"]) for candle in candles]
    lows = [float(candle["low"]) for candle in candles]
    volumes = [float(candle["volume"]) for candle in candles]

    current_price = closes[-1]
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    ema200 = ema(closes, 200)
    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)
    rsi14 = rsi(closes, 14)
    macd_result = macd(closes)
    bands = bollinger_bands(closes)
    atr14 = atr(highs, lows, closes, 14)
    adx14 = adx(highs, lows, closes, 14)
    average_volume20 = sma(volumes, 20)

    trend = "neutral"
    if ema20 is not None and ema50 is not None:
        trend = "bullish" if ema20 > ema50 else "bearish" if ema20 < ema50 else "neutral"

    momentum = "neutral"
    if rsi14 is not None:
        if rsi14 >= 70:
            momentum = "overbought"
        elif rsi14 <= 30:
            momentum = "oversold"
        elif rsi14 > 55:
            momentum = "bullish"
        elif rsi14 < 45:
            momentum = "bearish"

    volatility = "normal"
    if bands is not None:
        volatility = "high" if bands.width_percent >= 8 else "low" if bands.width_percent <= 2 else "normal"

    trend_strength = "unknown"
    if adx14 is not None:
        trend_strength = "strong" if adx14 >= 25 else "weak"

    return {
        "price": Decimal(str(current_price)),
        "candle_open_time": candles[-1]["open_time"],
        "candle_close_time": candles[-1]["close_time"],
        "moving_averages": {
            "ema20": _rounded(ema20),
            "ema50": _rounded(ema50),
            "ema200": _rounded(ema200),
            "sma20": _rounded(sma20),
            "sma50": _rounded(sma50),
        },
        "rsi14": _rounded(rsi14, 4),
        "macd": None
        if macd_result is None
        else {
            "macd": _rounded(macd_result.macd),
            "signal": _rounded(macd_result.signal),
            "histogram": _rounded(macd_result.histogram),
        },
        "bollinger": None
        if bands is None
        else {
            "upper": _rounded(bands.upper),
            "middle": _rounded(bands.middle),
            "lower": _rounded(bands.lower),
            "width_percent": _rounded(bands.width_percent, 4),
        },
        "atr14": _rounded(atr14),
        "atr_percent": _rounded((atr14 / current_price * 100) if atr14 and current_price else None, 4),
        "adx14": _rounded(adx14, 4),
        "volume": {
            "current": Decimal(str(volumes[-1])),
            "average20": _rounded(average_volume20),
            "ratio": _rounded((volumes[-1] / average_volume20) if average_volume20 else None, 4),
        },
        "market_state": {
            "trend": trend,
            "momentum": momentum,
            "volatility": volatility,
            "trend_strength": trend_strength,
        },
    }
