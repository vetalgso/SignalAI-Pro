from fastapi import APIRouter, Query

from app.backtesting.service import run_backtest
from app.services.binance_market import BinanceMarketService

router = APIRouter(prefix="/backtest", tags=["Backtesting"])

@router.get("")
async def backtest(
    symbol: str = Query("BTCUSDT", min_length=5, max_length=20),
    interval: str = Query("1h"),
    limit: int = Query(500, ge=250, le=1000),
):
    service = BinanceMarketService()
    candles = await service.klines(symbol.upper(), interval, limit)
    result = run_backtest(candles)
    return {"symbol": symbol.upper(), "interval": interval, **result}
