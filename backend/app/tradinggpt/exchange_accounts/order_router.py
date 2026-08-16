from __future__ import annotations

from typing import Annotated, NoReturn

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user,
)
from app.core.config import settings
from app.database.session import get_db
from app.models.user import User
from app.tradinggpt.orders.journal_service import (
    JournaledOrderService,
)
from app.tradinggpt.orders.models import (
    OrderIntent,
)
from app.tradinggpt.orders.repository import (
    TradingOrderRepository,
)
from app.tradinggpt.orders.risk import (
    OrderRiskPolicy,
)
from app.tradinggpt.orders.schemas import (
    OrderCancelResponse,
    OrderExecuteResponse,
    OrderJournalResponse,
    OrderPreviewResponse,
    OrderStatusResponse,
)

from .router import build_service
from .schemas import (
    ExchangeAccountOrderExecuteRequest,
    ExchangeAccountOrderRequest,
)
from .service import (
    ExchangeAccountNotFoundError,
    ExchangeConnectionError,
    ExchangeTradingUnavailableError,
    LiveExchangeExecutionDisabledError,
    UnsafeExchangePermissionsError,
)


router = APIRouter(
    prefix="/exchange/accounts",
    tags=[
        "TradingGPT Exchange Orders"
    ],
)


def build_order_risk_policy(
) -> OrderRiskPolicy:
    return OrderRiskPolicy.configured(
        execution_enabled=(
            settings
            .testnet_order_execution_enabled
        ),
        max_order_notional=(
            settings
            .testnet_max_order_notional
        ),
        allowed_symbols=(
            settings
            .testnet_allowed_symbols
        ),
    )


def raise_exchange_order_http_error(
    db: Session,
    exc: Exception,
) -> NoReturn:
    db.rollback()

    if isinstance(
        exc,
        ExchangeAccountNotFoundError,
    ):
        status_code = (
            status.HTTP_404_NOT_FOUND
        )
    elif isinstance(
        exc,
        (
            ExchangeTradingUnavailableError,
            LiveExchangeExecutionDisabledError,
            UnsafeExchangePermissionsError,
        ),
    ):
        status_code = (
            status.HTTP_409_CONFLICT
        )
    elif isinstance(
        exc,
        ExchangeConnectionError,
    ):
        status_code = (
            status.HTTP_502_BAD_GATEWAY
        )
    else:
        status_code = (
            status.HTTP_400_BAD_REQUEST
        )

    raise HTTPException(
        status_code=status_code,
        detail=str(exc),
    ) from exc


@router.get(
    "/{account_id}/orders/history",
    response_model=list[
        OrderJournalResponse
    ],
)
def list_exchange_account_order_history(
    account_id: int,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
    ),
    symbol: str | None = Query(
        default=None,
    ),
    order_status: str | None = Query(
        default=None,
        alias="status",
    ),
) -> list[OrderJournalResponse]:
    try:
        build_service(db).get(
            account_id=account_id,
            user_id=current_user.id,
        )
    except ExchangeAccountNotFoundError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc

    repository = TradingOrderRepository(
        db,
        user_id=current_user.id,
        exchange_account_id=account_id,
    )

    orders = repository.list_recent(
        limit=limit,
        exchange="BINANCE",
        symbol=(
            symbol.upper()
            if symbol is not None
            else None
        ),
        status=order_status,
    )

    return [
        OrderJournalResponse.model_validate(
            JournaledOrderService.serialize(
                order
            )
        )
        for order in orders
    ]


@router.get(
    (
        "/{account_id}/orders/history/"
        "{journal_id}"
    ),
    response_model=OrderJournalResponse,
)
def get_exchange_account_order_history(
    account_id: int,
    journal_id: int,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
) -> OrderJournalResponse:
    try:
        build_service(db).get(
            account_id=account_id,
            user_id=current_user.id,
        )
    except ExchangeAccountNotFoundError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc

    repository = TradingOrderRepository(
        db,
        user_id=current_user.id,
        exchange_account_id=account_id,
    )

    order = repository.get_by_id(
        journal_id
    )

    if order is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Order journal entry "
                "was not found."
            ),
        )

    return OrderJournalResponse.model_validate(
        JournaledOrderService.serialize(
            order
        )
    )


@router.get(
    "/{account_id}/orders/open",
    response_model=list[
        OrderExecuteResponse
    ],
)
def list_exchange_account_open_orders(
    account_id: int,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
    symbol: str | None = Query(
        default=None,
    ),
) -> list[OrderExecuteResponse]:
    try:
        execution = build_service(
            db
        ).order_execution_service(
            account_id=account_id,
            user_id=current_user.id,
        )

        results = (
            execution.list_open_orders(
                exchange="BINANCE",
                symbol=(
                    symbol.upper()
                    if symbol is not None
                    else None
                ),
            )
        )
    except (
        ExchangeAccountNotFoundError,
        ExchangeTradingUnavailableError,
        LiveExchangeExecutionDisabledError,
        UnsafeExchangePermissionsError,
        ExchangeConnectionError,
        ValueError,
    ) as exc:
        raise_exchange_order_http_error(
            db,
            exc,
        )

    return [
        OrderExecuteResponse.model_validate(
            result.to_dict()
        )
        for result in results
    ]


@router.get(
    "/{account_id}/orders/{order_id}",
    response_model=OrderStatusResponse,
)
def get_exchange_account_order(
    account_id: int,
    order_id: str,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
    symbol: str = Query(
        ...,
        min_length=1,
    ),
) -> OrderStatusResponse:
    try:
        execution = build_service(
            db
        ).order_execution_service(
            account_id=account_id,
            user_id=current_user.id,
        )

        result = execution.get_order(
            exchange="BINANCE",
            symbol=symbol.upper(),
            order_id=order_id,
        )
    except (
        ExchangeAccountNotFoundError,
        ExchangeTradingUnavailableError,
        LiveExchangeExecutionDisabledError,
        UnsafeExchangePermissionsError,
        ExchangeConnectionError,
        ValueError,
    ) as exc:
        raise_exchange_order_http_error(
            db,
            exc,
        )

    return OrderStatusResponse.model_validate(
        result.to_dict()
    )


@router.delete(
    "/{account_id}/orders/{order_id}",
    response_model=OrderCancelResponse,
)
def cancel_exchange_account_order(
    account_id: int,
    order_id: str,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
    symbol: str = Query(
        ...,
        min_length=1,
    ),
) -> OrderCancelResponse:
    try:
        execution = build_service(
            db
        ).order_execution_service(
            account_id=account_id,
            user_id=current_user.id,
        )

        result = execution.cancel_order(
            exchange="BINANCE",
            symbol=symbol.upper(),
            order_id=order_id,
        )
    except (
        ExchangeAccountNotFoundError,
        ExchangeTradingUnavailableError,
        LiveExchangeExecutionDisabledError,
        UnsafeExchangePermissionsError,
        ExchangeConnectionError,
        ValueError,
    ) as exc:
        raise_exchange_order_http_error(
            db,
            exc,
        )

    return OrderCancelResponse.model_validate(
        result.to_dict()
    )


@router.post(
    "/{account_id}/orders/execute",
    response_model=OrderJournalResponse,
)
def execute_exchange_account_order(
    account_id: int,
    request: (
        ExchangeAccountOrderExecuteRequest
    ),
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
) -> OrderJournalResponse:
    try:
        execution = build_service(
            db
        ).order_execution_service(
            account_id=account_id,
            user_id=current_user.id,
        )

        journal = JournaledOrderService(
            repository=(
                TradingOrderRepository(
                    db,
                    user_id=current_user.id,
                    exchange_account_id=(
                        account_id
                    ),
                )
            ),
            execution_service=execution,
            risk_policy=(
                build_order_risk_policy()
            ),
        )

        result = journal.execute(
            request
        )
    except ExchangeAccountNotFoundError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc
    except (
        ExchangeTradingUnavailableError,
        LiveExchangeExecutionDisabledError,
        UnsafeExchangePermissionsError,
    ) as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ExchangeConnectionError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise

    return OrderJournalResponse.model_validate(
        result
    )


@router.post(
    "/{account_id}/orders/preview",
    response_model=OrderPreviewResponse,
)
def preview_exchange_account_order(
    account_id: int,
    request: ExchangeAccountOrderRequest,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
) -> OrderPreviewResponse:
    try:
        execution = build_service(
            db
        ).order_execution_service(
            account_id=account_id,
            user_id=current_user.id,
        )

        intent = OrderIntent(
            **request.model_dump()
        )

        preview = (
            build_order_risk_policy()
            .apply(
                execution.preview(intent)
            )
        )
    except ExchangeAccountNotFoundError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=str(exc),
        ) from exc
    except (
        ExchangeTradingUnavailableError,
        LiveExchangeExecutionDisabledError,
        UnsafeExchangePermissionsError,
    ) as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ExchangeConnectionError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return OrderPreviewResponse.model_validate(
        preview.to_dict()
    )
