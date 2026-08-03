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

from .event_repository import (
    PositionEventRepository,
)
from .monitor import PositionMonitorService
from .preview_monitor import (
    LivePositionPreviewService,
)
from .live_monitor import (
    BinanceLivePriceProvider,
    LivePositionMonitorService,
)
from .repository import TradingPositionRepository
from .schemas import (
    PositionCloseRequest,
    PositionCreateRequest,
    PositionPriceUpdateRequest,
    PositionResponse,
    PositionMonitorRequest,
    PositionMonitorResponse,
    PositionEventResponse,
    LivePositionMonitorRequest,
    LivePositionMonitorResponse,
    LivePositionPreviewResponse,
)
from .service import PositionService


router = APIRouter(
    prefix="/positions",
    tags=["TradingGPT Positions"],
)


def _service(
    db: Session,
) -> PositionService:
    return PositionService(
        repository=TradingPositionRepository(db)
    )


@router.get(
    "",
    response_model=list[PositionResponse],
)
def list_positions(
    position_status: str | None = Query(
        default=None,
        alias="status",
    ),
    exchange: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
    ),
    db: Session = Depends(get_db),
) -> list[PositionResponse]:
    results = _service(db).list_positions(
        status=position_status,
        exchange=exchange,
        symbol=symbol,
        limit=limit,
    )

    return [
        PositionResponse.model_validate(result)
        for result in results
    ]


@router.post(
    "",
    response_model=PositionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_position(
    request: PositionCreateRequest,
    db: Session = Depends(get_db),
) -> PositionResponse:
    try:
        result = _service(db).create(request)
    except Exception:
        db.rollback()
        raise

    return PositionResponse.model_validate(result)


@router.get(
    "/{position_id}",
    response_model=PositionResponse,
)
def get_position(
    position_id: int,
    db: Session = Depends(get_db),
) -> PositionResponse:
    result = _service(db).get(position_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Trading position not found: "
                f"{position_id}."
            ),
        )

    return PositionResponse.model_validate(result)


@router.post(
    "/{position_id}/price",
    response_model=PositionResponse,
)
def update_position_price(
    position_id: int,
    request: PositionPriceUpdateRequest,
    db: Session = Depends(get_db),
) -> PositionResponse:
    try:
        result = _service(db).update_price(
            position_id=position_id,
            current_price=request.current_price,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Trading position not found: "
                f"{position_id}."
            ),
        )

    return PositionResponse.model_validate(result)


@router.post(
    "/{position_id}/close",
    response_model=PositionResponse,
)
def close_position(
    position_id: int,
    request: PositionCloseRequest,
    db: Session = Depends(get_db),
) -> PositionResponse:
    try:
        result = _service(db).close(
            position_id=position_id,
            exit_price=request.exit_price,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Trading position not found: "
                f"{position_id}."
            ),
        )

    return PositionResponse.model_validate(result)


@router.post(
    "/monitor",
    response_model=PositionMonitorResponse,
)
def monitor_positions(
    request: PositionMonitorRequest,
    db: Session = Depends(get_db),
) -> PositionMonitorResponse:
    service = PositionMonitorService(
        position_repository=(
            TradingPositionRepository(db)
        ),
        event_repository=(
            PositionEventRepository(db)
        ),
    )

    try:
        result = service.monitor(
            prices=request.prices,
            exchange=request.exchange,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise

    return PositionMonitorResponse.model_validate(
        result
    )


@router.get(
    "/events",
    response_model=list[PositionEventResponse],
)
def list_position_events(
    position_id: int | None = Query(
        default=None,
        ge=1,
    ),
    event_type: str | None = Query(
        default=None,
    ),
    limit: int = Query(
        default=200,
        ge=1,
        le=2000,
    ),
    db: Session = Depends(get_db),
) -> list[PositionEventResponse]:
    service = PositionMonitorService(
        position_repository=(
            TradingPositionRepository(db)
        ),
        event_repository=(
            PositionEventRepository(db)
        ),
    )

    results = service.list_events(
        position_id=position_id,
        event_type=event_type,
        limit=limit,
    )

    return [
        PositionEventResponse.model_validate(
            result
        )
        for result in results
    ]


@router.get(
    "/{position_id}/events",
    response_model=list[PositionEventResponse],
)
def list_events_for_position(
    position_id: int,
    limit: int = Query(
        default=200,
        ge=1,
        le=2000,
    ),
    db: Session = Depends(get_db),
) -> list[PositionEventResponse]:
    service = PositionMonitorService(
        position_repository=(
            TradingPositionRepository(db)
        ),
        event_repository=(
            PositionEventRepository(db)
        ),
    )

    results = service.list_events(
        position_id=position_id,
        event_type=None,
        limit=limit,
    )

    return [
        PositionEventResponse.model_validate(
            result
        )
        for result in results
    ]


@router.post(
    "/monitor/live",
    response_model=LivePositionMonitorResponse,
)
async def monitor_positions_live(
    request: LivePositionMonitorRequest,
    db: Session = Depends(get_db),
) -> LivePositionMonitorResponse:
    position_repository = (
        TradingPositionRepository(db)
    )
    event_repository = (
        PositionEventRepository(db)
    )

    monitor_service = PositionMonitorService(
        position_repository=(
            position_repository
        ),
        event_repository=event_repository,
    )

    service = LivePositionMonitorService(
        position_repository=(
            position_repository
        ),
        monitor_service=monitor_service,
        price_provider=(
            BinanceLivePriceProvider()
        ),
    )

    try:
        result = await service.monitor(
            exchange=request.exchange,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise

    return (
        LivePositionMonitorResponse
        .model_validate(result)
    )


@router.post(
    "/monitor/live/preview",
    response_model=LivePositionPreviewResponse,
)
async def preview_positions_live(
    request: LivePositionMonitorRequest,
    db: Session = Depends(get_db),
) -> LivePositionPreviewResponse:
    service = LivePositionPreviewService(
        position_repository=(
            TradingPositionRepository(db)
        ),
        price_provider=(
            BinanceLivePriceProvider()
        ),
    )

    try:
        result = await service.preview(
            exchange=request.exchange,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise

    return (
        LivePositionPreviewResponse
        .model_validate(result)
    )
