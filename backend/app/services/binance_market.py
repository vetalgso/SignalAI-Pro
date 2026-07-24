from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
import time

import httpx
from fastapi import HTTPException, status

from app.core.config import settings


class BinanceMarketService:
    """Small async client for Binance public Spot market-data endpoints."""

    _pairs_cache: list[dict[str, str]] | None = None
    _pairs_cache_expires_at: float = 0.0

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.binance_market_base_url).rstrip("/")
        self.timeout = httpx.Timeout(settings.binance_request_timeout_seconds)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"User-Agent": "SignalAI-Pro/2.0.0-beta.1"},
            ) as client:
                response = await client.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Binance market-data request timed out",
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not connect to Binance market-data API",
            ) from exc

        if response.status_code == 400:
            detail = "Binance rejected the market-data request"
            try:
                payload = response.json()
                detail = payload.get("msg", detail)
            except ValueError:
                pass
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

        if response.status_code >= 500:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Binance market-data API is temporarily unavailable",
            )

        try:
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Unexpected Binance response: HTTP {response.status_code}",
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Binance returned invalid JSON",
            ) from exc

    async def ping(self) -> bool:
        await self._get("/api/v3/ping")
        return True


    async def trading_pairs(self) -> list[dict[str, str]]:
        now = time.monotonic()
        if self.__class__._pairs_cache is not None and now < self.__class__._pairs_cache_expires_at:
            return self.__class__._pairs_cache

        payload = await self._get("/api/v3/exchangeInfo")
        pairs: list[dict[str, str]] = []
        for item in payload.get("symbols", []):
            if item.get("status") != "TRADING":
                continue
            if item.get("isSpotTradingAllowed") is False:
                continue
            permissions = item.get("permissions") or []
            if permissions and "SPOT" not in permissions:
                continue
            symbol = item.get("symbol")
            base_asset = item.get("baseAsset")
            quote_asset = item.get("quoteAsset")
            if not all(isinstance(value, str) and value for value in (symbol, base_asset, quote_asset)):
                continue
            pairs.append({
                "symbol": symbol,
                "base_asset": base_asset,
                "quote_asset": quote_asset,
                "status": item.get("status", "TRADING"),
            })

        pairs.sort(key=lambda pair: (pair["quote_asset"], pair["base_asset"]))
        self.__class__._pairs_cache = pairs
        self.__class__._pairs_cache_expires_at = now + 300
        return pairs

    async def ticker_price(self, symbol: str) -> dict[str, str]:
        payload = await self._get("/api/v3/ticker/price", {"symbol": symbol})
        return {"symbol": payload["symbol"], "price": payload["price"]}

    async def klines(self, symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
        payload = await self._get(
            "/api/v3/klines",
            {"symbol": symbol, "interval": interval, "limit": limit},
        )

        candles: list[dict[str, Any]] = []
        for row in payload:
            try:
                candles.append(
                    {
                        "open_time": row[0],
                        "open": Decimal(row[1]),
                        "high": Decimal(row[2]),
                        "low": Decimal(row[3]),
                        "close": Decimal(row[4]),
                        "volume": Decimal(row[5]),
                        "close_time": row[6],
                        "quote_asset_volume": Decimal(row[7]),
                        "trade_count": row[8],
                        "taker_buy_base_volume": Decimal(row[9]),
                        "taker_buy_quote_volume": Decimal(row[10]),
                    }
                )
            except (IndexError, InvalidOperation, TypeError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Binance returned an unexpected kline format",
                ) from exc
        return candles
