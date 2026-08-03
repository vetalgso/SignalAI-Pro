from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.tradinggpt.engine.router import (
    analyze_and_execute,
)
from app.tradinggpt.risk.models import (
    AccountRiskContext,
    RiskLimits,
)

from .schemas import (
    SafeSchedulerCycleRequest,
    SafeSchedulerCycleResponse,
)
from .service import SafeSchedulerCycleService


router = APIRouter(
    prefix="/scheduler",
    tags=["TradingGPT Scheduler"],
)


@router.post(
    "/cycle",
    response_model=SafeSchedulerCycleResponse,
)
def run_scheduler_cycle(
    request: SafeSchedulerCycleRequest,
    db: Session = Depends(get_db),
) -> SafeSchedulerCycleResponse:
    risk_request = request.runtime_risk

    account = AccountRiskContext(
        equity=risk_request.equity,
        peak_equity=risk_request.peak_equity,
        daily_pnl=risk_request.daily_pnl,
        open_positions=(
            risk_request.open_positions
        ),
        current_exposure_value=(
            risk_request.current_exposure_value
        ),
        correlated_exposure_value=(
            risk_request
            .correlated_exposure_value
        ),
    )

    limits = RiskLimits(
        max_daily_loss_percent=(
            risk_request
            .max_daily_loss_percent
        ),
        max_drawdown_percent=(
            risk_request
            .max_drawdown_percent
        ),
        max_total_exposure_percent=(
            risk_request
            .max_total_exposure_percent
        ),
        max_correlated_exposure_percent=(
            risk_request
            .max_correlated_exposure_percent
        ),
        max_open_positions=(
            risk_request.max_open_positions
        ),
        minimum_position_value=(
            risk_request
            .minimum_position_value
        ),
    )

    def execute_callback(
        dry_run: bool,
    ) -> dict[str, object]:
        safe_request = (
            request.analysis.model_copy(
                update={"dry_run": dry_run}
            )
        )

        response = analyze_and_execute(
            request=safe_request,
            db=db,
        )

        return response.model_dump(
            mode="json"
        )

    service = SafeSchedulerCycleService(
        execute_callback=execute_callback,
    )

    try:
        result = service.run(
            account=account,
            limits=limits,
        )
    except Exception:
        db.rollback()
        raise

    return (
        SafeSchedulerCycleResponse
        .model_validate(result)
    )
