from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.indicators.service import calculate_indicator_snapshot
from app.tradinggpt.data.binance_provider import BinanceMarketDataProvider
from app.tradinggpt.data.models import MarketDataWarning, MarketSnapshot
from app.tradinggpt.data.provider import MarketDataProvider


class MarketDataError(RuntimeError):
    """Raised when a usable market snapshot cannot be constructed."""


class MarketDataService:
    DEFAULT_TIMEOUT_SECONDS = 10.0
    MINIMUM_CANDLES = 50

    def __init__(
        self,
        provider: MarketDataProvider | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.provider = provider or BinanceMarketDataProvider()
        self.timeout_seconds = timeout_seconds

    async def get_market_snapshot(
        self,
        asset: str,
        interval: str = "1h",
        candle_limit: int = 250,
    ) -> MarketSnapshot:
        normalized_asset = self._normalize_asset(asset)
        symbol = self._to_spot_symbol(normalized_asset)
        fetched_at = datetime.now(timezone.utc)

        try:
            candles = await asyncio.wait_for(
                self.provider.get_candles(
                    symbol=symbol,
                    interval=interval,
                    limit=candle_limit,
                ),
                timeout=self.timeout_seconds,
            )
        except TimeoutError as exc:
            raise MarketDataError(
                f"Market-data request timed out for {symbol} {interval}"
            ) from exc
        except Exception as exc:
            raise MarketDataError(
                f"Market-data provider failed for {symbol} {interval}: "
                f"{type(exc).__name__}"
            ) from exc

        if not candles:
            raise MarketDataError(
                f"Market-data provider returned no candles for {symbol} {interval}"
            )

        warnings: list[MarketDataWarning] = []

        if len(candles) < self.MINIMUM_CANDLES:
            warnings.append(
                MarketDataWarning(
                    code="insufficient_history",
                    message=(
                        f"Only {len(candles)} candles were returned; "
                        f"at least {self.MINIMUM_CANDLES} are recommended"
                    ),
                )
            )

        try:
            indicators = calculate_indicator_snapshot(candles)
        except Exception as exc:
            raise MarketDataError(
                f"Indicator calculation failed for {symbol}: {type(exc).__name__}"
            ) from exc

        price = self._resolve_price(indicators, candles)
        volume_ratio = self._resolve_volume_ratio(indicators)

        if price <= 0:
            warnings.append(
                MarketDataWarning(
                    code="invalid_price",
                    message="The latest market price is unavailable or invalid",
                )
            )

        if volume_ratio is None:
            warnings.append(
                MarketDataWarning(
                    code="missing_volume_ratio",
                    message="Volume ratio could not be calculated",
                )
            )

        quality = self._calculate_quality(
            candles=candles,
            price=price,
            volume_ratio=volume_ratio,
            warnings=warnings,
        )

        return MarketSnapshot(
            asset=normalized_asset,
            symbol=symbol,
            interval=interval,
            candle_limit=candle_limit,
            price=price,
            candles=candles,
            indicators=indicators,
            volume_ratio=volume_ratio,
            source=self.provider.name,
            fetched_at=fetched_at,
            age_seconds=0.0,
            from_cache=False,
            data_quality=quality,
            warnings=warnings,
        )

    @classmethod
    def _normalize_asset(cls, asset: str) -> str:
        value = asset.strip().upper()

        if not value:
            raise ValueError("Asset must not be empty")

        if value.endswith("USDT"):
            value = value[:-4]

        if not value or not value.isalnum():
            raise ValueError(f"Unsupported asset: {asset}")

        return value

    @staticmethod
    def _to_spot_symbol(asset: str) -> str:
        return f"{asset}USDT"

    @staticmethod
    def _resolve_price(
        indicators: dict[str, Any],
        candles: list[dict[str, Any]],
    ) -> float:
        indicator_price = indicators.get("price")

        if indicator_price is not None:
            try:
                return float(indicator_price)
            except (TypeError, ValueError):
                pass

        try:
            return float(candles[-1]["close"])
        except (KeyError, TypeError, ValueError, IndexError):
            return 0.0

    @staticmethod
    def _resolve_volume_ratio(indicators: dict[str, Any]) -> float | None:
        volume = indicators.get("volume")

        if not isinstance(volume, dict):
            return None

        ratio = volume.get("ratio")

        if ratio is None:
            return None

        try:
            return round(float(ratio), 4)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _calculate_quality(
        cls,
        candles: list[dict[str, Any]],
        price: float,
        volume_ratio: float | None,
        warnings: list[MarketDataWarning],
    ) -> int:
        quality = 100

        if len(candles) < cls.MINIMUM_CANDLES:
            quality -= 35
        elif len(candles) < 200:
            quality -= 10

        if price <= 0:
            quality -= 50

        if volume_ratio is None:
            quality -= 10

        required_fields = {"open", "high", "low", "close", "volume"}
        malformed = sum(
            1
            for candle in candles
            if not required_fields.issubset(candle)
        )

        if malformed:
            malformed_ratio = malformed / max(len(candles), 1)
            quality -= min(30, round(malformed_ratio * 100))

            warnings.append(
                MarketDataWarning(
                    code="malformed_candles",
                    message=f"{malformed} candles contain missing fields",
                )
            )

        return max(0, min(100, quality))
