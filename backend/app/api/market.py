from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.schemas.market import (
    ALLOWED_KLINE_INTERVALS,
    KlineResponse,
    MarketStatus,
    TickerPrice,
    TradingPairsResponse,
)
from app.services.binance_market import BinanceMarketService

router = APIRouter(prefix="/market", tags=["Market Data"])


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not normalized or not normalized.isalnum() or len(normalized) > 20:
        raise HTTPException(
            status_code=422,
            detail="Symbol must contain only letters and numbers",
        )
    return normalized


@router.get("/status", response_model=MarketStatus)
async def market_status() -> MarketStatus:
    service = BinanceMarketService()
    connected = await service.ping()
    return MarketStatus(
        connected=connected,
        market_data_url=settings.binance_market_base_url,
    )


@router.get("/symbols", response_model=TradingPairsResponse)
async def trading_pairs(
    quote_asset: Annotated[str | None, Query(description="Optional quote asset filter, e.g. USDT")] = None,
    search: Annotated[str | None, Query(description="Optional symbol/base asset search")] = None,
) -> TradingPairsResponse:
    pairs = await BinanceMarketService().trading_pairs()
    if quote_asset:
        quote = quote_asset.strip().upper()
        pairs = [pair for pair in pairs if pair["quote_asset"] == quote]
    if search:
        query = search.strip().upper()
        pairs = [
            pair for pair in pairs
            if query in pair["symbol"] or query in pair["base_asset"]
        ]
    return TradingPairsResponse(
        count=len(pairs),
        quote_assets=sorted({pair["quote_asset"] for pair in pairs}),
        pairs=pairs,
    )


@router.get("/ticker", response_model=TickerPrice)
async def ticker_price(
    symbol: Annotated[str, Query(description="Spot symbol, for example BTCUSDT")] = "BTCUSDT",
) -> TickerPrice:
    normalized_symbol = normalize_symbol(symbol)
    result = await BinanceMarketService().ticker_price(normalized_symbol)
    return TickerPrice(**result)


@router.get("/klines", response_model=KlineResponse)
async def klines(
    symbol: Annotated[str, Query(description="Spot symbol, for example BTCUSDT")] = "BTCUSDT",
    interval: Annotated[str, Query(description="Candle interval, for example 1m, 15m, 1h, 1d")] = "1h",
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> KlineResponse:
    normalized_symbol = normalize_symbol(symbol)
    if interval not in ALLOWED_KLINE_INTERVALS:
        allowed = ", ".join(sorted(ALLOWED_KLINE_INTERVALS))
        raise HTTPException(status_code=422, detail=f"Unsupported interval. Allowed: {allowed}")

    candles = await BinanceMarketService().klines(normalized_symbol, interval, limit)
    return KlineResponse(
        symbol=normalized_symbol,
        interval=interval,
        limit=len(candles),
        candles=candles,
    )
