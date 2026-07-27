from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.tradinggpt.exchanges import (
    create_order_execution_service,
)

from .execution_service import UnsupportedExchangeError
from .models import OrderIntent
from .schemas import (
    OrderExecuteRequest,
    OrderExecuteResponse,
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
