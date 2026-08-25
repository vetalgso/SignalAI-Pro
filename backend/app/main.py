from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.tradinggpt.router import router as tradinggpt_router
from app.tradinggpt.engine.router import router as tradinggpt_engine_router
from app.tradinggpt.exchange_accounts.order_router import (
    router as tradinggpt_exchange_account_orders_router,
)
from app.tradinggpt.exchange_accounts.router import router as tradinggpt_exchange_accounts_router
from app.tradinggpt.orders.reconciliation_background import (
    order_reconciliation_background_loop,
)
from app.tradinggpt.orders.router import router as tradinggpt_orders_router
from app.tradinggpt.portfolio_sync.router import router as tradinggpt_portfolio_router
from app.tradinggpt.positions.router import router as tradinggpt_positions_router
from app.tradinggpt.risk.router import router as tradinggpt_risk_router
from app.tradinggpt.scheduler.router import router as tradinggpt_scheduler_router
from app.tradinggpt.signals.router import router as tradinggpt_signals_router
from app.tradinggpt.signals.background import (
    signal_lifecycle_background_loop,
)
from app.tradinggpt.scheduler.background_registry import (
    scheduler_background_loop,
)
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




@asynccontextmanager
async def lifespan(
    _: FastAPI,
) -> AsyncIterator[None]:
    scheduler_loop_started = False
    signal_loop_started = False
    reconciliation_loop_started = False

    if settings.scheduler_background_loop_enabled:
        scheduler_loop_started = await (
            scheduler_background_loop.start()
        )

    if getattr(
        settings,
        "signal_tracking_enabled",
        False,
    ):
        signal_loop_started = await (
            signal_lifecycle_background_loop
            .start()
        )

    if getattr(
        settings,
        "order_reconciliation_background_enabled",
        False,
    ):
        reconciliation_loop_started = await (
            order_reconciliation_background_loop
            .start()
        )

    try:
        yield
    finally:
        if reconciliation_loop_started:
            await (
                order_reconciliation_background_loop
                .stop()
            )

        if signal_loop_started:
            await (
                signal_lifecycle_background_loop
                .stop()
            )

        if scheduler_loop_started:
            await scheduler_background_loop.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Backend API for SignalAI Pro.",
    lifespan=lifespan,
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

app.include_router(tradinggpt_router, prefix="/api/v3")
app.include_router(tradinggpt_engine_router, prefix="/api/v3")
app.include_router(tradinggpt_exchange_accounts_router, prefix="/api/v3")
app.include_router(
    tradinggpt_exchange_account_orders_router,
    prefix="/api/v3",
)
app.include_router(tradinggpt_orders_router, prefix="/api/v3")
app.include_router(tradinggpt_portfolio_router, prefix="/api/v3")
app.include_router(tradinggpt_positions_router, prefix="/api/v3")
app.include_router(tradinggpt_risk_router, prefix="/api/v3")
app.include_router(tradinggpt_scheduler_router, prefix="/api/v3")
app.include_router(tradinggpt_signals_router, prefix="/api/v3")
