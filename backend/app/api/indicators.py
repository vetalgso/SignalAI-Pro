from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.market import normalize_symbol
from app.indicators.service import calculate_indicator_snapshot
from app.schemas.indicators import IndicatorResponse
from app.schemas.market import ALLOWED_KLINE_INTERVALS
from app.services.binance_market import BinanceMarketService

router = APIRouter(prefix="/indicators", tags=["Technical Indicators"])


@router.get("", response_model=IndicatorResponse)
async def indicator_snapshot(
    symbol: Annotated[str, Query(description="Spot symbol, for example BTCUSDT")] = "BTCUSDT",
    interval: Annotated[str, Query(description="Candle interval, for example 15m, 1h, 4h, 1d")] = "1h",
    limit: Annotated[int, Query(ge=200, le=1000, description="Candles used for calculations")] = 250,
) -> IndicatorResponse:
    normalized_symbol = normalize_symbol(symbol)
    if interval not in ALLOWED_KLINE_INTERVALS:
        allowed = ", ".join(sorted(ALLOWED_KLINE_INTERVALS))
        raise HTTPException(status_code=422, detail=f"Unsupported interval. Allowed: {allowed}")

    candles = await BinanceMarketService().klines(normalized_symbol, interval, limit)
    snapshot = calculate_indicator_snapshot(candles)
    return IndicatorResponse(
        symbol=normalized_symbol,
        interval=interval,
        candles_used=len(candles),
        **snapshot,
    )
