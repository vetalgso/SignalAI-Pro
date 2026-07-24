from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    ai_router,
    backtesting_router,
    auth_router,
    exchange_router,
    health_router,
    forecasts_router,
    news_router,
    indicators_router,
    market_router,
    settings_router,
    signal_engine_router,
    signals_router,
    strategies_router,
    users_router,
)
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Backend API for SignalAI Pro.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(forecasts_router, prefix="/api/v2")
app.include_router(news_router, prefix="/api/v2")
app.include_router(backtesting_router, prefix="/api/v1")
app.include_router(market_router, prefix="/api/v1")
app.include_router(indicators_router, prefix="/api/v1")
app.include_router(signal_engine_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(signals_router, prefix="/api/v1")
app.include_router(exchange_router, prefix="/api/v1")
app.include_router(strategies_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
