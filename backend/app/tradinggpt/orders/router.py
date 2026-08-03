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
from app.tradinggpt.exchanges import (
    create_order_execution_service,
    create_portfolio_sync_service,
)

from .execution_service import (
    UnsupportedExchangeError,
    UnsupportedOrderOperationError,
)
from .journal_service import JournaledOrderService
from .models import ExchangeName, OrderIntent
from .repository import TradingOrderRepository
from .schemas import (
    JournalOrderExecuteRequest,
    OrderCancelResponse,
    OrderExecuteRequest,
    OrderExecuteResponse,
    OrderJournalResponse,
    OrderPreviewResponse,
    OrderStatusResponse,
    SymbolTradingRulesResponse,
)


router = APIRouter(
    prefix="/orders",
    tags=["TradingGPT Orders"],
)

order_execution_service = (
    create_order_execution_service()
)
portfolio_sync_service = (
    create_portfolio_sync_service()
)


def _bad_request(
    exc: Exception,
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


def _journal_service(
    db: Session,
) -> JournaledOrderService:
    return JournaledOrderService(
        repository=TradingOrderRepository(db),
        execution_service=order_execution_service,
        portfolio_sync_service=(
            portfolio_sync_service
        ),
    )


@router.post(
    "/execute",
    response_model=OrderJournalResponse,
)
def execute_order(
    request: JournalOrderExecuteRequest,
    db: Session = Depends(get_db),
) -> OrderJournalResponse:
    try:
        result = _journal_service(db).execute(
            request
        )
    except (
        UnsupportedExchangeError,
        UnsupportedOrderOperationError,
    ) as exc:
        db.rollback()
        raise _bad_request(exc) from exc
    except Exception:
        db.rollback()
        raise

    return OrderJournalResponse.model_validate(
        result
    )


@router.get(
    "/history",
    response_model=list[OrderJournalResponse],
)
def list_order_history(
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
    ),
    exchange: str | None = Query(
        default=None,
    ),
    symbol: str | None = Query(
        default=None,
    ),
    order_status: str | None = Query(
        default=None,
        alias="status",
    ),
    db: Session = Depends(get_db),
) -> list[OrderJournalResponse]:
    results = _journal_service(
        db
    ).list_history(
        limit=limit,
        exchange=exchange,
        symbol=symbol,
        status=order_status,
    )

    return [
        OrderJournalResponse.model_validate(
            item
        )
        for item in results
    ]


@router.get(
    "/history/{journal_id}",
    response_model=OrderJournalResponse,
)
def get_order_history(
    journal_id: int,
    db: Session = Depends(get_db),
) -> OrderJournalResponse:
    result = _journal_service(
        db
    ).get_history(journal_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Order journal entry not found: "
                f"{journal_id}."
            ),
        )

    return OrderJournalResponse.model_validate(
        result
    )


@router.post(
    "/preview",
    response_model=OrderPreviewResponse,
)
def preview_order(
    request: OrderExecuteRequest,
) -> OrderPreviewResponse:
    try:
        result = order_execution_service.preview(
            OrderIntent(**request.model_dump())
        )
    except (
        UnsupportedExchangeError,
        UnsupportedOrderOperationError,
    ) as exc:
        raise _bad_request(exc) from exc

    return OrderPreviewResponse.model_validate(
        result.to_dict()
    )


@router.get(
    "/open",
    response_model=list[OrderExecuteResponse],
)
def list_open_orders(
    exchange: ExchangeName = Query(...),
    symbol: str | None = Query(default=None),
) -> list[OrderExecuteResponse]:
    try:
        results = (
            order_execution_service
            .list_open_orders(
                exchange=exchange,
                symbol=(
                    symbol.upper()
                    if symbol
                    else None
                ),
            )
        )
    except (
        UnsupportedExchangeError,
        UnsupportedOrderOperationError,
    ) as exc:
        raise _bad_request(exc) from exc

    return [
        OrderExecuteResponse.model_validate(
            result.to_dict()
        )
        for result in results
    ]


@router.get(
    "/rules/{symbol}",
    response_model=SymbolTradingRulesResponse,
)
def get_symbol_rules(
    symbol: str,
    exchange: ExchangeName = Query(...),
) -> SymbolTradingRulesResponse:
    try:
        result = (
            order_execution_service
            .get_symbol_rules(
                exchange=exchange,
                symbol=symbol.upper(),
            )
        )
    except (
        UnsupportedExchangeError,
        UnsupportedOrderOperationError,
    ) as exc:
        raise _bad_request(exc) from exc

    return (
        SymbolTradingRulesResponse
        .model_validate(result.to_dict())
    )


@router.get(
    "/{order_id}",
    response_model=OrderStatusResponse,
)
def get_order(
    order_id: str,
    exchange: ExchangeName = Query(...),
    symbol: str = Query(..., min_length=1),
) -> OrderStatusResponse:
    try:
        result = order_execution_service.get_order(
            exchange=exchange,
            symbol=symbol.upper(),
            order_id=order_id,
        )
    except (
        UnsupportedExchangeError,
        UnsupportedOrderOperationError,
    ) as exc:
        raise _bad_request(exc) from exc

    return OrderStatusResponse.model_validate(
        result.to_dict()
    )


@router.delete(
    "/{order_id}",
    response_model=OrderCancelResponse,
)
def cancel_order(
    order_id: str,
    exchange: ExchangeName = Query(...),
    symbol: str = Query(..., min_length=1),
) -> OrderCancelResponse:
    try:
        result = (
            order_execution_service.cancel_order(
                exchange=exchange,
                symbol=symbol.upper(),
                order_id=order_id,
            )
        )
    except (
        UnsupportedExchangeError,
        UnsupportedOrderOperationError,
    ) as exc:
        raise _bad_request(exc) from exc

    return OrderCancelResponse.model_validate(
        result.to_dict()
    )
