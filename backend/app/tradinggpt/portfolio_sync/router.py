from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.tradinggpt.exchanges.registry import (
    create_portfolio_sync_service,
)

from .history_service import PortfolioHistoryService
from .models import PortfolioSnapshot
from .repository import PortfolioSnapshotRepository
from .schemas import (
    PortfolioAnalyticsResponse,
    PortfolioSnapshotRecordResponse,
)
from .service import (
    PortfolioSyncService,
    UnsupportedPortfolioSourceError,
)


router = APIRouter(
    prefix="/portfolio",
    tags=["TradingGPT Portfolio Sync"],
)


def build_portfolio_sync_service() -> PortfolioSyncService:
    return create_portfolio_sync_service()


portfolio_sync_service = build_portfolio_sync_service()


def _history_service(
    db: Session,
) -> PortfolioHistoryService:
    return PortfolioHistoryService(
        repository=PortfolioSnapshotRepository(db)
    )


@router.get(
    "/snapshot",
    response_model=PortfolioSnapshot,
)
def get_portfolio_snapshot(
    source: str = Query(
        default="PAPER",
        min_length=1,
    ),
    persist: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> PortfolioSnapshot:
    try:
        snapshot = (
            portfolio_sync_service.get_snapshot(
                source=source
            )
        )

        if persist:
            _history_service(db).save(snapshot)

        return snapshot
    except UnsupportedPortfolioSourceError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Failed to synchronize portfolio from "
                f"{source.upper()}: {exc}"
            ),
        ) from exc


@router.get(
    "/history",
    response_model=list[
        PortfolioSnapshotRecordResponse
    ],
)
def list_portfolio_history(
    source: str | None = Query(default=None),
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
    ),
    db: Session = Depends(get_db),
) -> list[PortfolioSnapshotRecordResponse]:
    records = _history_service(
        db
    ).list_history(
        source=source,
        limit=limit,
    )

    return [
        PortfolioSnapshotRecordResponse
        .model_validate(
            PortfolioHistoryService.serialize(
                record
            )
        )
        for record in records
    ]


@router.get(
    "/history/{snapshot_id}",
    response_model=PortfolioSnapshotRecordResponse,
)
def get_portfolio_history(
    snapshot_id: int,
    db: Session = Depends(get_db),
) -> PortfolioSnapshotRecordResponse:
    record = _history_service(db).get(
        snapshot_id
    )

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Portfolio snapshot not found: "
                f"{snapshot_id}."
            ),
        )

    return (
        PortfolioSnapshotRecordResponse
        .model_validate(
            PortfolioHistoryService.serialize(
                record
            )
        )
    )


@router.get(
    "/analytics",
    response_model=PortfolioAnalyticsResponse,
)
def get_portfolio_analytics(
    source: str = Query(
        default="PAPER",
        min_length=1,
    ),
    limit: int = Query(
        default=1000,
        ge=1,
        le=10000,
    ),
    db: Session = Depends(get_db),
) -> PortfolioAnalyticsResponse:
    result = _history_service(db).analytics(
        source=source,
        limit=limit,
    )

    return (
        PortfolioAnalyticsResponse
        .model_validate(result)
    )
