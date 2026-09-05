from __future__ import annotations

from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.tradinggpt.facade import tradinggpt

from .generator import (
    TradingSignalGenerator,
)
from .lifecycle import (
    SignalLifecycleTracker,
)
from .runtime_metrics import (
    PROMETHEUS_CONTENT_TYPE,
    SignalPipelineMetricsService,
)
from .scanner_background import (
    signal_scanner_background_loop,
)
from .telegram_background import (
    telegram_signal_background_loop,
)
from .repository import (
    TradingSignalRepository,
)
from .schemas import (
    SignalCreateRequest,
    SignalEventResponse,
    SignalPageResponse,
    SignalRefreshResponse,
    SignalResponse,
    SignalScanRequest,
    SignalScanResponse,
    SignalTransitionRequest,
)
from .service import (
    DuplicateSignalError,
    InvalidSignalTransitionError,
    SignalNotFoundError,
    TradingSignalService,
)


router = APIRouter(
    prefix="/signals",
    tags=["TradingGPT Signals"],
)


def _service(
    db: Session,
) -> TradingSignalService:
    return TradingSignalService(
        repository=(
            TradingSignalRepository(db)
        )
    )


@router.post(
    "",
    response_model=SignalResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_signal(
    request: SignalCreateRequest,
    db: Session = Depends(get_db),
) -> SignalResponse:
    try:
        signal = _service(db).create(
            request
        )
    except DuplicateSignalError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail={
                "message": str(exc),
                "existing_signal_id": (
                    exc.existing_signal_id
                ),
            },
        ) from exc
    except Exception:
        db.rollback()
        raise

    return SignalResponse.model_validate(
        signal
    )


@router.get(
    "",
    response_model=SignalPageResponse,
)
def list_signals(
    exchange: str | None = Query(
        default=None
    ),
    symbol: str | None = Query(
        default=None
    ),
    timeframe: str | None = Query(
        default=None
    ),
    side: str | None = Query(
        default=None
    ),
    signal_status: str | None = Query(
        default=None,
        alias="status",
    ),
    risk_level: str | None = Query(
        default=None
    ),
    min_confidence: Decimal | None = Query(
        default=None,
        ge=0,
        le=100,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    db: Session = Depends(get_db),
) -> SignalPageResponse:
    items, total = _service(db).list(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        side=side,
        status=signal_status,
        risk_level=risk_level,
        min_confidence=min_confidence,
        limit=limit,
        offset=offset,
    )

    return SignalPageResponse(
        items=[
            SignalResponse.model_validate(
                item
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )




@router.post(
    "/scan",
    response_model=SignalScanResponse,
)
async def scan_and_create_signals(
    request: SignalScanRequest,
    db: Session = Depends(get_db),
) -> SignalScanResponse:
    try:
        scan_result = await tradinggpt.scan_market(
            assets=request.assets or None,
            risk_level=request.risk_level,
            limit=request.limit,
        )

        if not isinstance(
            scan_result,
            dict,
        ):
            raise TypeError(
                "Market scanner returned "
                "an invalid result."
            )

        result = TradingSignalGenerator(
            _service(db)
        ).persist_scan(
            scan_result=scan_result,
            min_confidence=(
                request.min_confidence
            ),
        )
    except Exception:
        db.rollback()
        raise

    return SignalScanResponse(
        universe_source=result[
            "universe_source"
        ],
        universe_assets=result[
            "universe_assets"
        ],
        scanned_assets=(
            result["scanned_assets"]
        ),
        successful_assets=(
            result["successful_assets"]
        ),
        failed_assets=(
            result["failed_assets"]
        ),
        opportunities_found=(
            result[
                "opportunities_found"
            ]
        ),
        evaluated_candidates=result[
            "evaluated_candidates"
        ],
        created_count=(
            result["created_count"]
        ),
        duplicate_count=(
            result["duplicate_count"]
        ),
        skipped_count=(
            result["skipped_count"]
        ),
        created=[
            SignalResponse.model_validate(
                signal
            )
            for signal in result["created"]
        ],
        duplicates=result["duplicates"],
        skipped=result["skipped"],
        scanner_errors=(
            result["scanner_errors"]
        ),
        rejection_reasons=result[
            "rejection_reasons"
        ],
    )




@router.post(
    "/refresh",
    response_model=SignalRefreshResponse,
)
async def refresh_signal_lifecycle(
    db: Session = Depends(get_db),
) -> SignalRefreshResponse:
    try:
        result = await SignalLifecycleTracker(
            TradingSignalRepository(db)
        ).refresh_all()
    except Exception:
        db.rollback()
        raise

    return SignalRefreshResponse.model_validate(
        result
    )


@router.get(
    "/runtime/metrics",
    response_class=Response,
)
def get_signal_runtime_metrics(
    db: Session = Depends(get_db),
) -> Response:
    metrics = SignalPipelineMetricsService(
        session=db,
        scanner_enabled=(
            settings
            .signal_scanner_background_enabled
        ),
        telegram_enabled=(
            settings.telegram_signal_enabled
        ),
        scanner_status_provider=(
            signal_scanner_background_loop
            .status
        ),
        telegram_status_provider=(
            telegram_signal_background_loop
            .status
        ),
    ).render()

    return Response(
        content=metrics,
        media_type=PROMETHEUS_CONTENT_TYPE,
    )


@router.get(
    "/{signal_id}",
    response_model=SignalResponse,
)
def get_signal(
    signal_id: int,
    db: Session = Depends(get_db),
) -> SignalResponse:
    try:
        signal = _service(db).get(
            signal_id
        )
    except SignalNotFoundError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc

    return SignalResponse.model_validate(
        signal
    )


@router.get(
    "/{signal_id}/events",
    response_model=list[
        SignalEventResponse
    ],
)
def list_signal_events(
    signal_id: int,
    db: Session = Depends(get_db),
) -> list[SignalEventResponse]:
    try:
        events = _service(db).events(
            signal_id
        )
    except SignalNotFoundError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc

    return [
        SignalEventResponse.model_validate(
            event
        )
        for event in events
    ]


@router.post(
    "/{signal_id}/status",
    response_model=SignalResponse,
)
def transition_signal(
    signal_id: int,
    request: SignalTransitionRequest,
    db: Session = Depends(get_db),
) -> SignalResponse:
    try:
        signal = _service(db).transition(
            signal_id=signal_id,
            request=request,
        )
    except SignalNotFoundError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc
    except InvalidSignalTransitionError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise

    return SignalResponse.model_validate(
        signal
    )
