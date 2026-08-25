from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
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
from app.tradinggpt.orders.execution_models import (
    OrderExecutionResult,
)
from app.tradinggpt.orders.execution_service import (
    OrderExecutionService,
)
from app.tradinggpt.orders.journal_service import (
    JournaledOrderService,
    OrderReconciliationUnavailableError,
)
from app.tradinggpt.orders.models import (
    OrderIntent,
)
from app.tradinggpt.orders.reconciliation_background import (
    order_reconciliation_background_loop,
)
from app.tradinggpt.orders.reconciliation_batch_repository import (
    OrderReconciliationBatchRepository,
)
from app.tradinggpt.orders.repository import (
    TradingOrderRepository,
)
from app.tradinggpt.orders.risk import (
    OrderRiskPolicy,
    OrderRiskUsage,
    OrderRiskUsageUnavailableError,
    count_verified_open_orders,
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
    ExchangeAccountOrderReconciliationBatchResponse,
    ExchangeAccountOrderReconciliationStatusResponse,
    ExchangeAccountOrderRiskResponse,
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
        max_daily_notional=(
            settings
            .testnet_max_daily_notional
        ),
        max_open_orders=(
            settings
            .testnet_max_open_orders
        ),
        allowed_symbols=(
            settings
            .testnet_allowed_symbols
        ),
    )


def build_order_risk_usage(
    db: Session,
    *,
    execution_service: OrderExecutionService,
    user_id: int,
    account_id: int,
) -> OrderRiskUsage:
    repository = TradingOrderRepository(
        db,
        user_id=user_id,
        exchange_account_id=account_id,
    )

    stored_usage = (
        repository.get_today_risk_usage()
    )
    remote_open_orders = (
        execution_service.list_open_orders(
            exchange="BINANCE",
            symbol=None,
        )
    )

    return OrderRiskUsage(
        daily_notional=(
            stored_usage.daily_notional
        ),
        open_orders=(
            count_verified_open_orders(
                remote_open_orders
            )
        ),
    )


def reconcile_exchange_order_result(
    db: Session,
    *,
    execution_service: OrderExecutionService,
    result: OrderExecutionResult,
    user_id: int,
    account_id: int,
) -> None:
    journal = JournaledOrderService(
        repository=TradingOrderRepository(
            db,
            user_id=user_id,
            exchange_account_id=account_id,
        ),
        execution_service=execution_service,
    )

    journal.reconcile_remote_result(
        result
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
        (
            ExchangeConnectionError,
            OrderReconciliationUnavailableError,
            OrderRiskUsageUnavailableError,
        ),
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
    "/{account_id}/orders/reconciliation/history",
    response_model=list[
        ExchangeAccountOrderReconciliationBatchResponse
    ],
)
def list_exchange_account_order_reconciliation_history(
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
    action: str | None = Query(
        default=None,
        min_length=1,
    ),
) -> list[
    ExchangeAccountOrderReconciliationBatchResponse
]:
    try:
        build_service(db).get(
            account_id=account_id,
            user_id=current_user.id,
        )
    except ExchangeAccountNotFoundError as exc:
        raise_exchange_order_http_error(
            db,
            exc,
        )

    batches = (
        OrderReconciliationBatchRepository(
            db
        )
        .list_recent(
            action=(
                action.upper()
                if action is not None
                else None
            ),
            limit=limit,
        )
    )

    return [
        ExchangeAccountOrderReconciliationBatchResponse(
            account_id=account_id,
            batch_id=batch.id,
            action=batch.action,
            source=batch.source,
            read_only=batch.read_only,
            scanned=batch.scanned,
            reconciled=batch.reconciled,
            skipped=batch.skipped,
            failed=batch.failed,
            errors=list(
                batch.errors or ()
            ),
            error_message=(
                batch.error_message
            ),
            started_at=batch.started_at,
            finished_at=batch.finished_at,
        )
        for batch in batches
    ]


@router.get(
    "/{account_id}/orders/reconciliation/status",
    response_model=(
        ExchangeAccountOrderReconciliationStatusResponse
    ),
)
def get_exchange_account_order_reconciliation_status(
    account_id: int,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
) -> ExchangeAccountOrderReconciliationStatusResponse:
    try:
        build_service(db).get(
            account_id=account_id,
            user_id=current_user.id,
        )
    except ExchangeAccountNotFoundError as exc:
        raise_exchange_order_http_error(
            db,
            exc,
        )

    loop_status = (
        order_reconciliation_background_loop
        .status()
    )

    return (
        ExchangeAccountOrderReconciliationStatusResponse(
            account_id=account_id,
            source="BINANCE_TESTNET",
            enabled=(
                settings
                .order_reconciliation_background_enabled
            ),
            read_only=True,
            poll_interval_seconds=(
                loop_status
                .poll_interval_seconds
            ),
            batch_size=(
                settings
                .order_reconciliation_batch_size
            ),
            running=loop_status.running,
            stopping=loop_status.stopping,
            iterations=loop_status.iterations,
            failed_ticks=(
                loop_status.failed_ticks
            ),
            started_at=loop_status.started_at,
            stopped_at=loop_status.stopped_at,
            last_tick_started_at=(
                loop_status
                .last_tick_started_at
            ),
            last_tick_finished_at=(
                loop_status
                .last_tick_finished_at
            ),
            last_action=(
                loop_status.last_action
            ),
            last_error=loop_status.last_error,
        )
    )


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
    "/{account_id}/orders/risk",
    response_model=(
        ExchangeAccountOrderRiskResponse
    ),
)
def get_exchange_account_order_risk(
    account_id: int,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
) -> ExchangeAccountOrderRiskResponse:
    try:
        execution = build_service(
            db
        ).order_execution_service(
            account_id=account_id,
            user_id=current_user.id,
        )

        policy = build_order_risk_policy()
        usage = build_order_risk_usage(
            db,
            execution_service=execution,
            user_id=current_user.id,
            account_id=account_id,
        )
    except (
        ExchangeAccountNotFoundError,
        ExchangeTradingUnavailableError,
        LiveExchangeExecutionDisabledError,
        UnsafeExchangePermissionsError,
        ExchangeConnectionError,
        OrderRiskUsageUnavailableError,
        ValueError,
    ) as exc:
        raise_exchange_order_http_error(
            db,
            exc,
        )

    now = datetime.now(timezone.utc)
    period_started_at = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    resets_at = (
        period_started_at
        + timedelta(days=1)
    )

    remaining_daily_notional = (
        max(
            0.0,
            policy.max_daily_notional
            - usage.daily_notional,
        )
        if policy.max_daily_notional
        is not None
        else None
    )

    remaining_open_order_slots = (
        max(
            0,
            policy.max_open_orders
            - usage.open_orders,
        )
        if policy.max_open_orders
        is not None
        else None
    )

    order_submission_available = (
        policy.execution_enabled
        and (
            remaining_daily_notional
            is None
            or remaining_daily_notional > 0
        )
        and (
            remaining_open_order_slots
            is None
            or remaining_open_order_slots > 0
        )
    )

    return ExchangeAccountOrderRiskResponse(
        source="BINANCE_TESTNET",
        execution_enabled=(
            policy.execution_enabled
        ),
        max_order_notional=(
            policy.max_order_notional
        ),
        daily_notional=(
            usage.daily_notional
        ),
        max_daily_notional=(
            policy.max_daily_notional
        ),
        remaining_daily_notional=(
            remaining_daily_notional
        ),
        open_orders=usage.open_orders,
        max_open_orders=(
            policy.max_open_orders
        ),
        remaining_open_order_slots=(
            remaining_open_order_slots
        ),
        allowed_symbols=sorted(
            policy.allowed_symbols
        ),
        order_submission_available=(
            order_submission_available
        ),
        period_started_at=(
            period_started_at
        ),
        resets_at=resets_at,
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
        OrderRiskUsageUnavailableError,
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

        reconcile_exchange_order_result(
            db,
            execution_service=execution,
            result=result,
            user_id=current_user.id,
            account_id=account_id,
        )
    except (
        ExchangeAccountNotFoundError,
        ExchangeTradingUnavailableError,
        LiveExchangeExecutionDisabledError,
        UnsafeExchangePermissionsError,
        ExchangeConnectionError,
        OrderReconciliationUnavailableError,
        OrderRiskUsageUnavailableError,
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

        reconcile_exchange_order_result(
            db,
            execution_service=execution,
            result=result,
            user_id=current_user.id,
            account_id=account_id,
        )
    except (
        ExchangeAccountNotFoundError,
        ExchangeTradingUnavailableError,
        LiveExchangeExecutionDisabledError,
        UnsafeExchangePermissionsError,
        ExchangeConnectionError,
        OrderReconciliationUnavailableError,
        OrderRiskUsageUnavailableError,
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
    except (
        ExchangeConnectionError,
        OrderRiskUsageUnavailableError,
    ) as exc:
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

        risk_usage = None

        if not intent.reduce_only:
            risk_usage = (
                build_order_risk_usage(
                    db,
                    execution_service=execution,
                    user_id=current_user.id,
                    account_id=account_id,
                )
            )

        preview = (
            build_order_risk_policy()
            .apply(
                execution.preview(intent),
                usage=risk_usage,
                increases_exposure=(
                    not intent.reduce_only
                ),
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
