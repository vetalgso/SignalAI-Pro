from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.market import normalize_symbol
from app.forecasting import ForecastService

router = APIRouter(prefix="/forecasts", tags=["Future Signals"])


@router.get("/current")
async def current_forecast(
    symbol: Annotated[str, Query()] = "BTCUSDT",
    horizons: Annotated[
        str,
        Query(description="Comma-separated forecast horizons in minutes"),
    ] = "15,30,60,120,240,1440,2880,7200,14400",
):
    normalized = normalize_symbol(symbol)
    try:
        values = sorted(set(int(value.strip()) for value in horizons.split(",") if value.strip()))
    except ValueError as exc:
        raise HTTPException(422, "Horizons must be integers") from exc

    if not values or any(value < 5 or value > 14_400 for value in values) or len(values) > 9:
        raise HTTPException(422, "Use 1-9 horizons between 5 and 14400 minutes")

    try:
        return await ForecastService().forecast(normalized, values)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
