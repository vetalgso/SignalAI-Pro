from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from app.tradinggpt.exchanges import create_order_execution_service
from .execution_service import UnsupportedExchangeError, UnsupportedOrderOperationError
from .models import ExchangeName, OrderIntent
from .schemas import (
    OrderCancelResponse,
    OrderExecuteRequest,
    OrderExecuteResponse,
    OrderPreviewResponse,
    OrderStatusResponse,
    SymbolTradingRulesResponse,
)

router = APIRouter(prefix="/orders", tags=["TradingGPT Orders"])
order_execution_service = create_order_execution_service()


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/execute", response_model=OrderExecuteResponse)
def execute_order(request: OrderExecuteRequest) -> OrderExecuteResponse:
    try:
        result = order_execution_service.execute(OrderIntent(**request.model_dump()))
    except (UnsupportedExchangeError, UnsupportedOrderOperationError) as exc:
        raise _bad_request(exc) from exc
    return OrderExecuteResponse.model_validate(result.to_dict())


@router.post("/preview", response_model=OrderPreviewResponse)
def preview_order(request: OrderExecuteRequest) -> OrderPreviewResponse:
    try:
        result = order_execution_service.preview(OrderIntent(**request.model_dump()))
    except (UnsupportedExchangeError, UnsupportedOrderOperationError) as exc:
        raise _bad_request(exc) from exc
    return OrderPreviewResponse.model_validate(result.to_dict())


@router.get("/open", response_model=list[OrderExecuteResponse])
def list_open_orders(exchange: ExchangeName = Query(...), symbol: str | None = Query(default=None)) -> list[OrderExecuteResponse]:
    try:
        results = order_execution_service.list_open_orders(exchange=exchange, symbol=symbol.upper() if symbol else None)
    except (UnsupportedExchangeError, UnsupportedOrderOperationError) as exc:
        raise _bad_request(exc) from exc
    return [OrderExecuteResponse.model_validate(result.to_dict()) for result in results]


@router.get("/rules/{symbol}", response_model=SymbolTradingRulesResponse)
def get_symbol_rules(symbol: str, exchange: ExchangeName = Query(...)) -> SymbolTradingRulesResponse:
    try:
        result = order_execution_service.get_symbol_rules(exchange=exchange, symbol=symbol.upper())
    except (UnsupportedExchangeError, UnsupportedOrderOperationError) as exc:
        raise _bad_request(exc) from exc
    return SymbolTradingRulesResponse.model_validate(result.to_dict())


@router.get("/{order_id}", response_model=OrderStatusResponse)
def get_order(order_id: str, exchange: ExchangeName = Query(...), symbol: str = Query(..., min_length=1)) -> OrderStatusResponse:
    try:
        result = order_execution_service.get_order(exchange=exchange, symbol=symbol.upper(), order_id=order_id)
    except (UnsupportedExchangeError, UnsupportedOrderOperationError) as exc:
        raise _bad_request(exc) from exc
    return OrderStatusResponse.model_validate(result.to_dict())


@router.delete("/{order_id}", response_model=OrderCancelResponse)
def cancel_order(order_id: str, exchange: ExchangeName = Query(...), symbol: str = Query(..., min_length=1)) -> OrderCancelResponse:
    try:
        result = order_execution_service.cancel_order(exchange=exchange, symbol=symbol.upper(), order_id=order_id)
    except (UnsupportedExchangeError, UnsupportedOrderOperationError) as exc:
        raise _bad_request(exc) from exc
    return OrderCancelResponse.model_validate(result.to_dict())
