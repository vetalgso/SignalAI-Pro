from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.market import normalize_symbol
from app.database.session import get_db
from app.models.signal import Signal
from app.models.user import User
from app.schemas.indicators import IndicatorResponse
from app.schemas.market import ALLOWED_KLINE_INTERVALS
from app.schemas.signal_engine import GeneratedSignalResponse, SignalAnalysisResponse
from app.signal_engine.service import build_signal_analysis
from app.tradinggpt.data import MarketDataService

router = APIRouter(prefix="/signal-engine", tags=["Signal Engine"])


async def _analyze(symbol: str, interval: str, limit: int) -> SignalAnalysisResponse:
    normalized_symbol = normalize_symbol(symbol)
    if interval not in ALLOWED_KLINE_INTERVALS:
        allowed = ", ".join(sorted(ALLOWED_KLINE_INTERVALS))
        raise HTTPException(status_code=422, detail=f"Unsupported interval. Allowed: {allowed}")

    snapshot = await MarketDataService().get_market_snapshot(
        asset=normalized_symbol.removesuffix("USDT"),
        interval=interval,
        candle_limit=limit,
    )

    indicators = IndicatorResponse(
        symbol=snapshot.symbol,
        interval=snapshot.interval,
        candles_used=len(snapshot.candles),
        **snapshot.indicators,
    )

    decision = build_signal_analysis(snapshot.indicators)
    return SignalAnalysisResponse(
        symbol=normalized_symbol,
        interval=interval,
        indicators=indicators,
        **decision,
    )


@router.get("/analyze", response_model=SignalAnalysisResponse)
async def analyze_signal(
    symbol: Annotated[str, Query(description="Spot symbol, for example BTCUSDT")] = "BTCUSDT",
    interval: Annotated[str, Query(description="Candle interval, for example 15m, 1h, 4h, 1d")] = "1h",
    limit: Annotated[int, Query(ge=200, le=1000)] = 250,
) -> SignalAnalysisResponse:
    return await _analyze(symbol, interval, limit)


@router.post(
    "/generate",
    response_model=GeneratedSignalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_signal(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    symbol: Annotated[str, Query(description="Spot symbol, for example BTCUSDT")] = "BTCUSDT",
    interval: Annotated[str, Query(description="Candle interval, for example 15m, 1h, 4h, 1d")] = "1h",
    limit: Annotated[int, Query(ge=200, le=1000)] = 250,
) -> GeneratedSignalResponse:
    del current_user  # Authentication is required; ownership will be added in a later migration.
    analysis = await _analyze(symbol, interval, limit)
    if analysis.action == "WAIT" or analysis.levels is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "No actionable signal is available",
                "action": analysis.action,
                "confidence": analysis.confidence,
                "reasons": analysis.reasons,
                "warnings": analysis.warnings,
            },
        )

    signal = Signal(
        symbol=analysis.symbol,
        timeframe=analysis.interval,
        strategy=analysis.strategy,
        side=analysis.action,
        entry_price=analysis.levels.entry,
        stop_loss=analysis.levels.stop_loss,
        take_profit=analysis.levels.take_profit,
        confidence=analysis.confidence,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return GeneratedSignalResponse(analysis=analysis, saved_signal=signal)
