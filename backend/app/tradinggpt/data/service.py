from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, ClassVar

from redis.asyncio import Redis

from app.core.config import settings

from app.indicators.service import calculate_indicator_snapshot
from app.tradinggpt.data.binance_provider import BinanceMarketDataProvider
from app.tradinggpt.data.models import MarketDataWarning, MarketSnapshot
from app.tradinggpt.data.provider import MarketDataProvider


class MarketDataError(RuntimeError):
    """Raised when a usable market snapshot cannot be constructed."""


class MarketDataService:
    DEFAULT_TIMEOUT_SECONDS = 10.0
    MINIMUM_CANDLES = 50
    CACHE_KEY_VERSION = "v1"

    CACHE_TTL_SECONDS: ClassVar[dict[str, int]] = {
        "1m": 20,
        "3m": 30,
        "5m": 30,
        "15m": 60,
        "30m": 90,
        "1h": 180,
        "2h": 240,
        "4h": 300,
        "6h": 420,
        "8h": 480,
        "12h": 600,
        "1d": 600,
        "3d": 900,
        "1w": 1_800,
        "1M": 3_600,
    }

    _shared_cache_client: ClassVar[Redis | None] = None

    def __init__(
        self,
        provider: MarketDataProvider | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        cache_client: Redis | None = None,
        cache_enabled: bool = True,
    ) -> None:
        self.provider = provider or BinanceMarketDataProvider()
        self.timeout_seconds = timeout_seconds
        self.cache_enabled = cache_enabled
        self.cache_client = cache_client

    async def get_market_snapshot(
        self,
        asset: str,
        interval: str = "1h",
        candle_limit: int = 250,
    ) -> MarketSnapshot:
        normalized_asset = self._normalize_asset(asset)
        symbol = self._to_spot_symbol(normalized_asset)

        cache_key = self._cache_key(
            symbol=symbol,
            interval=interval,
            candle_limit=candle_limit,
        )
        cached_snapshot = await self._load_cached_snapshot(cache_key)

        if cached_snapshot is not None:
            return cached_snapshot

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

        snapshot = MarketSnapshot(
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

        await self._store_cached_snapshot(
            key=cache_key,
            snapshot=snapshot,
            ttl_seconds=self._cache_ttl(interval),
        )

        return snapshot

    async def _load_cached_snapshot(
        self,
        key: str,
    ) -> MarketSnapshot | None:
        if not self.cache_enabled:
            return None

        try:
            client = self._get_cache_client()
            payload = await client.get(key)

            if not payload:
                return None

            snapshot = MarketSnapshot.model_validate_json(payload)
            fetched_at = snapshot.fetched_at

            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)

            age_seconds = max(
                0.0,
                (datetime.now(timezone.utc) - fetched_at).total_seconds(),
            )

            return snapshot.model_copy(
                update={
                    "fetched_at": fetched_at,
                    "age_seconds": round(age_seconds, 3),
                    "from_cache": True,
                }
            )
        except Exception:
            # Cache failures must never block live market-data loading.
            return None

    async def _store_cached_snapshot(
        self,
        key: str,
        snapshot: MarketSnapshot,
        ttl_seconds: int,
    ) -> None:
        if not self.cache_enabled:
            return

        try:
            client = self._get_cache_client()
            await client.set(
                key,
                snapshot.model_dump_json(),
                ex=ttl_seconds,
            )
        except Exception:
            # A valid live snapshot is still usable when Redis is unavailable.
            return

    def _get_cache_client(self) -> Redis:
        if self.cache_client is not None:
            return self.cache_client

        if self.__class__._shared_cache_client is None:
            self.__class__._shared_cache_client = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
            )

        return self.__class__._shared_cache_client

    @classmethod
    def _cache_key(
        cls,
        symbol: str,
        interval: str,
        candle_limit: int,
    ) -> str:
        return (
            "tradinggpt:market_snapshot:"
            f"{cls.CACHE_KEY_VERSION}:{symbol}:{interval}:{candle_limit}"
        )

    @classmethod
    def _cache_ttl(cls, interval: str) -> int:
        return cls.CACHE_TTL_SECONDS.get(interval, 120)

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
