from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


STRATEGY_NAME = "technical_confluence_v1"
SIGNAL_THRESHOLD = 60


def _decimal(value: float | Decimal) -> Decimal:
    return Decimal(str(value))


def _price(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def _add_reason(reasons: list[str], text: str) -> None:
    if text not in reasons:
        reasons.append(text)


def build_signal_analysis(snapshot: dict[str, Any]) -> dict[str, Any]:
    price = _decimal(snapshot["price"])
    moving = snapshot["moving_averages"]
    macd = snapshot.get("macd")
    rsi = snapshot.get("rsi14")
    atr_value = snapshot.get("atr14")
    adx_value = snapshot.get("adx14")
    volume_ratio = snapshot["volume"].get("ratio")

    long_score = 0
    short_score = 0
    long_reasons: list[str] = []
    short_reasons: list[str] = []
    warnings: list[str] = []

    ema20 = moving.get("ema20")
    ema50 = moving.get("ema50")
    ema200 = moving.get("ema200")

    if ema20 is not None and ema50 is not None:
        if ema20 > ema50:
            long_score += 20
            _add_reason(long_reasons, "EMA20 is above EMA50")
        elif ema20 < ema50:
            short_score += 20
            _add_reason(short_reasons, "EMA20 is below EMA50")

    if ema200 is not None:
        if price > _decimal(ema200):
            long_score += 15
            _add_reason(long_reasons, "Price is above EMA200")
        elif price < _decimal(ema200):
            short_score += 15
            _add_reason(short_reasons, "Price is below EMA200")

    if rsi is not None:
        if 52 <= rsi <= 68:
            long_score += 15
            _add_reason(long_reasons, f"RSI14 supports bullish momentum ({rsi:.2f})")
        elif 32 <= rsi <= 48:
            short_score += 15
            _add_reason(short_reasons, f"RSI14 supports bearish momentum ({rsi:.2f})")
        elif rsi > 70:
            warnings.append(f"RSI14 is overbought ({rsi:.2f})")
            short_score += 5
        elif rsi < 30:
            warnings.append(f"RSI14 is oversold ({rsi:.2f})")
            long_score += 5

    if macd is not None:
        histogram = macd["histogram"]
        if histogram > 0 and macd["macd"] > macd["signal"]:
            long_score += 20
            _add_reason(long_reasons, "MACD is bullish with a positive histogram")
        elif histogram < 0 and macd["macd"] < macd["signal"]:
            short_score += 20
            _add_reason(short_reasons, "MACD is bearish with a negative histogram")

    if adx_value is not None:
        if adx_value >= 25:
            if long_score > short_score:
                long_score += 15
                _add_reason(long_reasons, f"ADX14 confirms trend strength ({adx_value:.2f})")
            elif short_score > long_score:
                short_score += 15
                _add_reason(short_reasons, f"ADX14 confirms trend strength ({adx_value:.2f})")
        else:
            warnings.append(f"ADX14 indicates a weak or ranging market ({adx_value:.2f})")

    if volume_ratio is not None:
        if volume_ratio >= 1.10:
            if long_score > short_score:
                long_score += 15
                _add_reason(long_reasons, f"Volume is above its 20-period average ({volume_ratio:.2f}x)")
            elif short_score > long_score:
                short_score += 15
                _add_reason(short_reasons, f"Volume is above its 20-period average ({volume_ratio:.2f}x)")
        elif volume_ratio < 0.70:
            warnings.append(f"Current volume is low ({volume_ratio:.2f}x average)")

    long_score = min(long_score, 100)
    short_score = min(short_score, 100)

    action = "WAIT"
    winning_score = max(long_score, short_score)
    reasons: list[str] = []

    if long_score >= SIGNAL_THRESHOLD and long_score >= short_score + 15:
        action = "LONG"
        reasons = long_reasons
    elif short_score >= SIGNAL_THRESHOLD and short_score >= long_score + 15:
        action = "SHORT"
        reasons = short_reasons
    else:
        reasons = [
            "No direction reached the minimum confluence threshold",
            f"Long score: {long_score}; short score: {short_score}",
        ]

    confidence = float(winning_score if action != "WAIT" else max(0, winning_score - 10))
    levels = None

    if action != "WAIT" and atr_value is not None and atr_value > 0:
        atr_decimal = _decimal(atr_value)
        stop_distance = atr_decimal * Decimal("1.5")
        target_distance = stop_distance * Decimal("2")
        if action == "LONG":
            stop_loss = price - stop_distance
            take_profit = price + target_distance
        else:
            stop_loss = price + stop_distance
            take_profit = price - target_distance

        if stop_loss > 0 and take_profit > 0:
            levels = {
                "entry": _price(price),
                "stop_loss": _price(stop_loss),
                "take_profit": _price(take_profit),
                "risk_reward_ratio": 2.0,
            }
    elif action != "WAIT":
        warnings.append("ATR14 is unavailable; trade levels could not be calculated")
        action = "WAIT"
        reasons = ["Signal was rejected because risk levels could not be calculated"]
        confidence = 0.0

    return {
        "action": action,
        "confidence": round(confidence, 2),
        "strategy": STRATEGY_NAME,
        "score": {
            "long_score": long_score,
            "short_score": short_score,
            "threshold": SIGNAL_THRESHOLD,
        },
        "levels": levels,
        "reasons": reasons,
        "warnings": warnings,
    }
