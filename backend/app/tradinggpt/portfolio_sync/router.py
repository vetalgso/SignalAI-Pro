from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.tradinggpt.exchanges.registry import (
    create_portfolio_sync_service,
)

from .models import PortfolioSnapshot
from .service import (
    PortfolioSyncService,
    UnsupportedPortfolioSourceError,
)


router = APIRouter(
    prefix="/portfolio",
    tags=["TradingGPT Portfolio Sync"],
)


def build_portfolio_sync_service() -> PortfolioSyncService:
    """
    Application composition hook.

    Kept as a function so tests and future dependency injection can
    replace service construction without changing endpoint behavior.
    """

    return create_portfolio_sync_service()


portfolio_sync_service = build_portfolio_sync_service()


@router.get(
    "/snapshot",
    response_model=PortfolioSnapshot,
)
def get_portfolio_snapshot(
    source: str = Query(
        default="PAPER",
        min_length=1,
    ),
) -> PortfolioSnapshot:
    try:
        return portfolio_sync_service.get_snapshot(
            source=source
        )
    except UnsupportedPortfolioSourceError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to synchronize portfolio from "
                f"{source.upper()}: {exc}"
            ),
        ) from exc
