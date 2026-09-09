from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

from .models import (
    AccountRiskContext,
    RiskLimits,
)
from .runtime import RuntimeRiskGuard
from .schemas import (
    RuntimeRiskCheckRequest,
    RuntimeRiskCheckResponse,
)


router = APIRouter(
    prefix="/risk",
    tags=["TradingGPT Risk"],
)


@router.post(
    "/runtime/check",
    response_model=RuntimeRiskCheckResponse,
)
def check_runtime_risk(
    request: RuntimeRiskCheckRequest,
) -> RuntimeRiskCheckResponse:
    account = AccountRiskContext(
        equity=request.equity,
        peak_equity=request.peak_equity,
        daily_pnl=request.daily_pnl,
        open_positions=request.open_positions,
        current_exposure_value=(
            request.current_exposure_value
        ),
        correlated_exposure_value=(
            request.correlated_exposure_value
        ),
    )

    limits = RiskLimits(
        max_daily_loss_percent=(
            request.max_daily_loss_percent
        ),
        max_drawdown_percent=(
            request.max_drawdown_percent
        ),
        max_total_exposure_percent=(
            request.max_total_exposure_percent
        ),
        max_correlated_exposure_percent=(
            request
            .max_correlated_exposure_percent
        ),
        max_open_positions=(
            request.max_open_positions
        ),
        minimum_position_value=(
            request.minimum_position_value
        ),
    )

    try:
        result = RuntimeRiskGuard.evaluate(
            account=account,
            limits=limits,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return RuntimeRiskCheckResponse.model_validate(
        result.to_dict()
    )
