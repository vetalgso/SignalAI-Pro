from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Sequence


Number = float | int


def _floats(values: Sequence[Number]) -> list[float]:
    return [float(value) for value in values]


def sma(values: Sequence[Number], period: int) -> float | None:
    data = _floats(values)
    if period <= 0 or len(data) < period:
        return None
    return sum(data[-period:]) / period


def ema_series(values: Sequence[Number], period: int) -> list[float | None]:
    data = _floats(values)
    if period <= 0 or len(data) < period:
        return [None] * len(data)

    result: list[float | None] = [None] * len(data)
    seed = sum(data[:period]) / period
    result[period - 1] = seed
    multiplier = 2 / (period + 1)
    previous = seed

    for index in range(period, len(data)):
        previous = ((data[index] - previous) * multiplier) + previous
        result[index] = previous
    return result


def ema(values: Sequence[Number], period: int) -> float | None:
    series = ema_series(values, period)
    return series[-1] if series else None


def rsi(values: Sequence[Number], period: int = 14) -> float | None:
    data = _floats(values)
    if period <= 0 or len(data) < period + 1:
        return None

    changes = [data[index] - data[index - 1] for index in range(1, len(data))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]

    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period

    for index in range(period, len(changes)):
        average_gain = ((average_gain * (period - 1)) + gains[index]) / period
        average_loss = ((average_loss * (period - 1)) + losses[index]) / period

    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


@dataclass(frozen=True)
class MacdResult:
    macd: float
    signal: float
    histogram: float


def macd(
    values: Sequence[Number],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> MacdResult | None:
    data = _floats(values)
    if len(data) < slow_period + signal_period - 1:
        return None

    fast = ema_series(data, fast_period)
    slow = ema_series(data, slow_period)
    macd_values: list[float] = []
    for fast_value, slow_value in zip(fast, slow, strict=True):
        if fast_value is not None and slow_value is not None:
            macd_values.append(fast_value - slow_value)

    signal_values = ema_series(macd_values, signal_period)
    signal_value = signal_values[-1]
    if signal_value is None:
        return None

    macd_value = macd_values[-1]
    return MacdResult(
        macd=macd_value,
        signal=signal_value,
        histogram=macd_value - signal_value,
    )


@dataclass(frozen=True)
class BollingerResult:
    upper: float
    middle: float
    lower: float
    width_percent: float


def bollinger_bands(
    values: Sequence[Number], period: int = 20, standard_deviations: float = 2.0
) -> BollingerResult | None:
    data = _floats(values)
    if period <= 0 or len(data) < period:
        return None

    window = data[-period:]
    middle = sum(window) / period
    variance = sum((value - middle) ** 2 for value in window) / period
    deviation = sqrt(variance)
    upper = middle + standard_deviations * deviation
    lower = middle - standard_deviations * deviation
    width_percent = ((upper - lower) / middle * 100) if middle else 0.0
    return BollingerResult(upper, middle, lower, width_percent)


def true_ranges(
    highs: Sequence[Number], lows: Sequence[Number], closes: Sequence[Number]
) -> list[float]:
    high_values = _floats(highs)
    low_values = _floats(lows)
    close_values = _floats(closes)
    if not (len(high_values) == len(low_values) == len(close_values)):
        raise ValueError("High, low and close arrays must have equal length")
    if not close_values:
        return []

    ranges = [high_values[0] - low_values[0]]
    for index in range(1, len(close_values)):
        ranges.append(
            max(
                high_values[index] - low_values[index],
                abs(high_values[index] - close_values[index - 1]),
                abs(low_values[index] - close_values[index - 1]),
            )
        )
    return ranges


def wilder_average(values: Sequence[Number], period: int) -> list[float | None]:
    data = _floats(values)
    if period <= 0 or len(data) < period:
        return [None] * len(data)

    result: list[float | None] = [None] * len(data)
    previous = sum(data[:period]) / period
    result[period - 1] = previous
    for index in range(period, len(data)):
        previous = ((previous * (period - 1)) + data[index]) / period
        result[index] = previous
    return result


def atr(
    highs: Sequence[Number], lows: Sequence[Number], closes: Sequence[Number], period: int = 14
) -> float | None:
    ranges = true_ranges(highs, lows, closes)
    averages = wilder_average(ranges, period)
    return averages[-1] if averages else None


def adx(
    highs: Sequence[Number], lows: Sequence[Number], closes: Sequence[Number], period: int = 14
) -> float | None:
    high_values = _floats(highs)
    low_values = _floats(lows)
    close_values = _floats(closes)
    if len(close_values) < period * 2 or not (
        len(high_values) == len(low_values) == len(close_values)
    ):
        return None

    plus_dm = [0.0]
    minus_dm = [0.0]
    for index in range(1, len(close_values)):
        upward = high_values[index] - high_values[index - 1]
        downward = low_values[index - 1] - low_values[index]
        plus_dm.append(upward if upward > downward and upward > 0 else 0.0)
        minus_dm.append(downward if downward > upward and downward > 0 else 0.0)

    atr_values = wilder_average(true_ranges(high_values, low_values, close_values), period)
    plus_values = wilder_average(plus_dm, period)
    minus_values = wilder_average(minus_dm, period)

    dx_values: list[float] = []
    for atr_value, plus_value, minus_value in zip(
        atr_values, plus_values, minus_values, strict=True
    ):
        if atr_value is None or plus_value is None or minus_value is None or atr_value == 0:
            continue
        plus_di = 100 * plus_value / atr_value
        minus_di = 100 * minus_value / atr_value
        denominator = plus_di + minus_di
        dx_values.append(0.0 if denominator == 0 else 100 * abs(plus_di - minus_di) / denominator)

    adx_values = wilder_average(dx_values, period)
    return adx_values[-1] if adx_values else None
