from __future__ import annotations

from math import exp, sqrt
from statistics import mean, pstdev
from typing import Any

from app.indicators.service import calculate_indicator_snapshot
from app.services.binance_market import BinanceMarketService


class ForecastService:
    """Transparent multi-timeframe heuristic forecast baseline.

    Short horizons use minute candles; multi-day horizons use broader candles so the
    model does not pretend that a few hours of one-minute history can describe ten days.
    """

    INTERVALS: tuple[tuple[int, str, int], ...] = (
        (240, "1m", 1),
        (1_440, "15m", 15),
        (2_880, "30m", 30),
        (7_200, "1h", 60),
        (14_400, "4h", 240),
    )

    async def forecast(self, symbol: str, horizons: list[int]) -> dict[str, Any]:
        market = BinanceMarketService()
        grouped: dict[str, tuple[int, list[int]]] = {}
        for horizon in horizons:
            interval, interval_minutes = self._interval_for_horizon(horizon)
            if interval not in grouped:
                grouped[interval] = (interval_minutes, [])
            grouped[interval][1].append(horizon)

        candles_by_interval: dict[str, list[dict[str, Any]]] = {}
        for interval in grouped:
            candles_by_interval[interval] = await market.klines(symbol, interval, 500)

        payload: list[dict[str, Any]] = []
        current_price = 0.0
        for interval, (interval_minutes, interval_horizons) in grouped.items():
            candles = candles_by_interval[interval]
            closes = [float(candle["close"]) for candle in candles]
            volumes = [float(candle["volume"]) for candle in candles]
            if len(closes) < 220:
                raise ValueError(f"Not enough {interval} candles for forecast")

            indicators = calculate_indicator_snapshot(candles)
            current = closes[-1]
            current_price = current
            returns = [closes[index] / closes[index - 1] - 1.0 for index in range(1, len(closes))]
            bar_volatility = pstdev(returns[-120:]) if len(returns) >= 2 else 0.0
            volume_ratio = volumes[-1] / max(mean(volumes[-20:]), 1e-12)
            trend = self._trend_score(indicators)

            for horizon in interval_horizons:
                horizon_bars = max(1, round(horizon / interval_minutes))
                momentum_window = max(3, min(horizon_bars, 60, len(closes) - 2))
                short_window = max(2, min(6, len(closes) - 2))
                momentum = closes[-1] / closes[-1 - momentum_window] - 1.0
                short_momentum = closes[-1] / closes[-1 - short_window] - 1.0
                volatility_scale = max(bar_volatility * sqrt(horizon_bars), 1e-6)
                momentum_score = max(-1.0, min(1.0, momentum / volatility_scale))
                short_score = max(-1.0, min(1.0, short_momentum / max(bar_volatility * sqrt(short_window), 1e-6)))
                volume_confirmation = max(-0.25, min(0.25, (volume_ratio - 1.0) * 0.25))

                raw = 0.46 * trend + 0.38 * momentum_score + 0.16 * short_score
                raw += volume_confirmation * (1 if raw >= 0 else -1)
                raw = max(-3.0, min(3.0, raw))

                up = 1 / (1 + exp(-1.6 * raw))
                down = 1 - up
                noise = min(0.62, max(0.08, 0.34 - abs(raw) * 0.12 + bar_volatility * 35))
                up *= 1 - noise
                down *= 1 - noise
                sideways = noise
                total = up + down + sideways
                up, down, sideways = up / total, down / total, sideways / total

                best = max((up, "UP"), (down, "DOWN"), (sideways, "SIDEWAYS"))
                direction = best[1] if best[0] >= 0.48 else "UNCERTAIN"
                expected_return = raw * volatility_scale * 0.72
                expected_price = current * (1 + expected_return)
                range_half = current * volatility_scale * 1.65

                payload.append(
                    {
                        "horizon_minutes": horizon,
                        "source_interval": interval,
                        "direction": direction,
                        "confidence": round(best[0] * 100),
                        "probabilities": {
                            "up": round(up, 4),
                            "down": round(down, 4),
                            "sideways": round(sideways, 4),
                        },
                        "expected_change_percent": round(expected_return * 100, 4),
                        "predicted_price": round(expected_price, 8),
                        "price_range": {
                            "low": round(expected_price - range_half, 8),
                            "high": round(expected_price + range_half, 8),
                        },
                        "risk_level": (
                            "high"
                            if volatility_scale > 0.035
                            else "elevated"
                            if volatility_scale > 0.015
                            else "normal"
                        ),
                        "components": {
                            "trend": round(trend, 3),
                            "momentum": round(momentum_score, 3),
                            "volume_ratio": round(volume_ratio, 3),
                        },
                    }
                )

        payload.sort(key=lambda item: item["horizon_minutes"])
        return {
            "symbol": symbol,
            "current_price": current_price,
            "model_version": "transparent_multitimeframe_forecast_v2",
            "disclaimer": "Probabilistic heuristic forecast; not financial advice.",
            "forecasts": payload,
        }

    @classmethod
    def _interval_for_horizon(cls, horizon: int) -> tuple[str, int]:
        for maximum, interval, interval_minutes in cls.INTERVALS:
            if horizon <= maximum:
                return interval, interval_minutes
        return "4h", 240

    @staticmethod
    def _trend_score(indicators: Any) -> float:
        moving_averages = indicators.get("moving_averages", {})
        price = float(indicators.get("price", 0) or 0)
        ema20 = float(moving_averages.get("ema20") or price)
        ema50 = float(moving_averages.get("ema50") or price)
        ema200 = float(moving_averages.get("ema200") or price)
        score = 0.0
        score += 0.45 if ema20 > ema50 else -0.45
        score += 0.35 if ema50 > ema200 else -0.35
        score += 0.20 if price > ema200 else -0.20
        return score
