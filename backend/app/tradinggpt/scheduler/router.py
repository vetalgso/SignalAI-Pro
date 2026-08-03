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
    SchedulerStateResponse,
    SchedulerStateUpdateRequest,
    SchedulerRunnerStatusResponse,
    SchedulerRunnerTickRequest,
    SchedulerRunnerTickResponse,
    SchedulerPayloadResponse,
    SchedulerPayloadUpsertRequest,
)
from .service import SafeSchedulerCycleService
from .journal_service import (
    JournaledSchedulerCycleService,
)
from .repository import SchedulerCycleRepository
from .state_repository import (
    SchedulerStateRepository,
)
from .state_service import SchedulerStateService
from .payload_repository import (
    SchedulerPayloadRepository,
)
from .payload_service import SchedulerPayloadService
from .runner_registry import (
    create_scheduler_runner,
)


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
        state_repository=(
            SchedulerStateRepository(db)
        ),
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


@router.get(
    "/state",
    response_model=SchedulerStateResponse,
)
def get_scheduler_state(
    db: Session = Depends(get_db),
) -> SchedulerStateResponse:
    service = SchedulerStateService(
        SchedulerStateRepository(db)
    )

    return SchedulerStateResponse.model_validate(
        service.get()
    )


@router.patch(
    "/state",
    response_model=SchedulerStateResponse,
)
def update_scheduler_state(
    request: SchedulerStateUpdateRequest,
    db: Session = Depends(get_db),
) -> SchedulerStateResponse:
    service = SchedulerStateService(
        SchedulerStateRepository(db)
    )

    try:
        result = service.update(
            enabled=request.enabled,
            interval_seconds=(
                request.interval_seconds
            ),
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return SchedulerStateResponse.model_validate(
        result
    )


@router.post(
    "/runner/tick",
    response_model=SchedulerRunnerTickResponse,
)
def run_scheduler_runner_tick(
    request: SchedulerRunnerTickRequest,
    db: Session = Depends(get_db),
) -> SchedulerRunnerTickResponse:
    runner = create_scheduler_runner(db)

    result = runner.tick(
        force=request.force
    )

    return (
        SchedulerRunnerTickResponse
        .model_validate(result)
    )


@router.get(
    "/runner/status",
    response_model=SchedulerRunnerStatusResponse,
)
def get_scheduler_runner_status(
    db: Session = Depends(get_db),
) -> SchedulerRunnerStatusResponse:
    runner = create_scheduler_runner(db)

    return (
        SchedulerRunnerStatusResponse
        .model_validate(
            runner.status().to_dict()
        )
    )


@router.get(
    "/payload",
    response_model=SchedulerPayloadResponse,
)
def get_scheduler_payload(
    db: Session = Depends(get_db),
) -> SchedulerPayloadResponse:
    service = SchedulerPayloadService(
        SchedulerPayloadRepository(db)
    )

    return SchedulerPayloadResponse.model_validate(
        service.get()
    )


@router.put(
    "/payload",
    response_model=SchedulerPayloadResponse,
)
def save_scheduler_payload(
    request: SchedulerPayloadUpsertRequest,
    db: Session = Depends(get_db),
) -> SchedulerPayloadResponse:
    service = SchedulerPayloadService(
        SchedulerPayloadRepository(db)
    )

    result = service.save(
        runtime_risk_payload=(
            request.runtime_risk.model_dump(
                mode="json"
            )
        ),
        analysis_payload=(
            request.analysis.model_dump(
                mode="json"
            )
        ),
    )

    return SchedulerPayloadResponse.model_validate(
        result
    )


@router.delete(
    "/payload",
    response_model=SchedulerPayloadResponse,
)
def clear_scheduler_payload(
    db: Session = Depends(get_db),
) -> SchedulerPayloadResponse:
    service = SchedulerPayloadService(
        SchedulerPayloadRepository(db)
    )

    return SchedulerPayloadResponse.model_validate(
        service.clear()
    )
