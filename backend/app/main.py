from fastapi import FastAPI

from app.api import (
    ai_router,
    exchange_router,
    health_router,
    settings_router,
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

app.include_router(health_router)
app.include_router(users_router, prefix="/api/v1")
app.include_router(signals_router, prefix="/api/v1")
app.include_router(exchange_router, prefix="/api/v1")
app.include_router(strategies_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
