from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user,
)
from app.core.config import settings
from app.database.session import get_db
from app.models.user import User
from app.tradinggpt.orders.models import (
    OrderIntent,
)
from app.tradinggpt.orders.schemas import (
    OrderPreviewResponse,
)
from app.tradinggpt.portfolio_sync.models import (
    PortfolioSnapshot,
)

from .crypto import (
    CredentialCipher,
    CredentialEncryptionError,
)
from .repository import (
    ExchangeAccountRepository,
)
from .schemas import (
    ExchangeAccountCreateRequest,
    ExchangeAccountDeleteResponse,
    ExchangeAccountOrderRequest,
    ExchangeAccountResponse,
)
from .service import (
    ExchangeAccountNotFoundError,
    ExchangeAccountService,
    ExchangeConnectionError,
    ExchangeTradingUnavailableError,
    LiveExchangeExecutionDisabledError,
    UnsafeExchangePermissionsError,
)


router = APIRouter(
    prefix="/exchange/accounts",
    tags=[
        "TradingGPT Exchange Accounts"
    ],
)


def build_service(
    db: Session,
) -> ExchangeAccountService:
    try:
        cipher = CredentialCipher(
            settings
            .exchange_credentials_encryption_key
        )
    except CredentialEncryptionError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Exchange credential encryption "
                "is not configured."
            ),
        ) from exc

    return ExchangeAccountService(
        repository=(
            ExchangeAccountRepository(db)
        ),
        cipher=cipher,
    )


def account_response(
    account: object,
) -> ExchangeAccountResponse:
    return (
        ExchangeAccountResponse
        .model_validate(account)
    )


@router.get(
    "",
    response_model=list[
        ExchangeAccountResponse
    ],
)
def list_exchange_accounts(
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
) -> list[ExchangeAccountResponse]:
    accounts = build_service(
        db
    ).list_for_user(current_user.id)

    return [
        account_response(account)
        for account in accounts
    ]


@router.post(
    "",
    response_model=ExchangeAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_exchange_account(
    request: ExchangeAccountCreateRequest,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
) -> ExchangeAccountResponse:
    try:
        account = build_service(
            db
        ).create_or_replace(
            user_id=current_user.id,
            request=request,
        )
    except Exception:
        db.rollback()
        raise

    return account_response(account)


@router.post(
    "/{account_id}/verify",
    response_model=ExchangeAccountResponse,
)
def verify_exchange_account(
    account_id: int,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
) -> ExchangeAccountResponse:
    try:
        account = build_service(
            db
        ).verify(
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
    except UnsafeExchangePermissionsError as exc:
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

    return account_response(account)


@router.get(
    "/{account_id}/portfolio",
    response_model=PortfolioSnapshot,
)
def get_exchange_portfolio(
    account_id: int,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
) -> PortfolioSnapshot:
    try:
        return build_service(
            db
        ).portfolio(
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
    except UnsafeExchangePermissionsError as exc:
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

        preview = execution.preview(
            OrderIntent(
                **request.model_dump()
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


@router.delete(
    "/{account_id}",
    response_model=(
        ExchangeAccountDeleteResponse
    ),
)
def delete_exchange_account(
    account_id: int,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
) -> ExchangeAccountDeleteResponse:
    try:
        build_service(db).delete(
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

    return ExchangeAccountDeleteResponse(
        deleted=True,
        account_id=account_id,
    )
