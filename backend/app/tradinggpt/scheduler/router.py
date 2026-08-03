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
from .journal_service import (
    JournaledSchedulerCycleService,
)
from .repository import SchedulerCycleRepository


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

    cycle_service = SafeSchedulerCycleService(
        execute_callback=execute_callback,
    )
    service = JournaledSchedulerCycleService(
        cycle_service=cycle_service,
        repository=SchedulerCycleRepository(db),
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


@router.get(
    "/cycles",
    response_model=list[SafeSchedulerCycleResponse],
)
def list_scheduler_cycles(
    cycle_status: str | None = Query(
        default=None,
        alias="status",
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
    ),
    db: Session = Depends(get_db),
) -> list[SafeSchedulerCycleResponse]:
    service = JournaledSchedulerCycleService(
        cycle_service=SafeSchedulerCycleService(
            execute_callback=lambda dry_run: {}
        ),
        repository=SchedulerCycleRepository(db),
    )

    return [
        SafeSchedulerCycleResponse.model_validate(
            item
        )
        for item in service.list_recent(
            status=cycle_status,
            limit=limit,
        )
    ]


@router.get(
    "/cycles/{cycle_id}",
    response_model=SafeSchedulerCycleResponse,
)
def get_scheduler_cycle(
    cycle_id: int,
    db: Session = Depends(get_db),
) -> SafeSchedulerCycleResponse:
    service = JournaledSchedulerCycleService(
        cycle_service=SafeSchedulerCycleService(
            execute_callback=lambda dry_run: {}
        ),
        repository=SchedulerCycleRepository(db),
    )

    result = service.get(cycle_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Scheduler cycle not found: "
                f"{cycle_id}."
            ),
        )

    return SafeSchedulerCycleResponse.model_validate(
        result
    )
