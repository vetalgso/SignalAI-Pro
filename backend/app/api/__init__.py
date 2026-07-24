from app.api.backtesting import router as backtesting_router
from app.api.auth import router as auth_router
from app.api.ai import router as ai_router
from app.api.exchange import router as exchange_router
from app.api.health import router as health_router
from app.api.forecasts import router as forecasts_router
from app.api.news import router as news_router
from app.api.indicators import router as indicators_router
from app.api.market import router as market_router
from app.api.settings import router as settings_router
from app.api.signal_engine import router as signal_engine_router
from app.api.signals import router as signals_router
from app.api.strategies import router as strategies_router
from app.api.users import router as users_router

__all__ = [
    "auth_router",
    "backtesting_router",
    "ai_router",
    "exchange_router",
    "health_router",
    "forecasts_router",
    "news_router",
    "indicators_router",
    "market_router",
    "settings_router",
    "signal_engine_router",
    "signals_router",
    "strategies_router",
    "users_router",
]
