from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.tradinggpt.exchanges import (
    create_order_execution_service,
)

from .execution_service import (
    UnsupportedExchangeError,
    UnsupportedOrderOperationError,
)
from .models import ExchangeName, OrderIntent
from .schemas import (
    OrderCancelResponse,
    OrderExecuteRequest,
    OrderExecuteResponse,
    OrderStatusResponse,
)


router = APIRouter(
    prefix="/orders",
    tags=["TradingGPT Orders"],
)

order_execution_service = create_order_execution_service()


@router.post(
    "/execute",
    response_model=OrderExecuteResponse,
)
def execute_order(
    request: OrderExecuteRequest,
) -> OrderExecuteResponse:
    intent = OrderIntent(
        **request.model_dump(),
    )

    try:
        result = order_execution_service.execute(intent)
    except UnsupportedExchangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return OrderExecuteResponse.model_validate(
        result.to_dict()
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

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
        result = order_execution_service.cancel_order(
            exchange=exchange,
            symbol=symbol.upper(),
            order_id=order_id,
        )
    except (
        UnsupportedExchangeError,
        UnsupportedOrderOperationError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return OrderCancelResponse.model_validate(
        result.to_dict()
    )
