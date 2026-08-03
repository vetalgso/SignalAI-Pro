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

from .repository import TradingPositionRepository
from .schemas import (
    PositionCloseRequest,
    PositionCreateRequest,
    PositionPriceUpdateRequest,
    PositionResponse,
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
