from app.api.ai import router as ai_router
from app.api.exchange import router as exchange_router
from app.api.health import router as health_router
from app.api.settings import router as settings_router
from app.api.signals import router as signals_router
from app.api.strategies import router as strategies_router
from app.api.users import router as users_router

__all__ = [
    "ai_router",
    "exchange_router",
    "health_router",
    "settings_router",
    "signals_router",
    "strategies_router",
    "users_router",
]
