from __future__ import annotations

from sqlalchemy.orm import Session

from app.tradinggpt.engine.router import (
    analyze_and_execute,
)
from app.tradinggpt.risk.models import (
    AccountRiskContext,
    RiskLimits,
)

from .journal_service import (
    JournaledSchedulerCycleService,
)
from .payload_repository import (
    SchedulerPayloadRepository,
)
from .repository import SchedulerCycleRepository
from .schemas import SafeSchedulerCycleRequest
from .service import SafeSchedulerCycleService
from .state_repository import (
    SchedulerStateRepository,
)


def execute_persisted_scheduler_payload(
    session: Session,
) -> dict[str, object] | None:
    stored = (
        SchedulerPayloadRepository(session)
        .get_or_create()
    )

    if (
        not stored.configured
        or stored.runtime_risk_payload is None
        or stored.analysis_payload is None
    ):
        return None

    request = SafeSchedulerCycleRequest.model_validate(
        {
            "runtime_risk": (
                stored.runtime_risk_payload
            ),
            "analysis": stored.analysis_payload,
        }
    )

    risk = request.runtime_risk

    account = AccountRiskContext(
        equity=risk.equity,
        peak_equity=risk.peak_equity,
        daily_pnl=risk.daily_pnl,
        open_positions=risk.open_positions,
        current_exposure_value=(
            risk.current_exposure_value
        ),
        correlated_exposure_value=(
            risk.correlated_exposure_value
        ),
    )

    limits = RiskLimits(
        max_daily_loss_percent=(
            risk.max_daily_loss_percent
        ),
        max_drawdown_percent=(
            risk.max_drawdown_percent
        ),
        max_total_exposure_percent=(
            risk.max_total_exposure_percent
        ),
        max_correlated_exposure_percent=(
            risk.max_correlated_exposure_percent
        ),
        max_open_positions=(
            risk.max_open_positions
        ),
        minimum_position_value=(
            risk.minimum_position_value
        ),
    )

    def execute_callback(
        dry_run: bool,
    ) -> dict[str, object]:
        safe_request = request.analysis.model_copy(
            update={"dry_run": dry_run}
        )

        response = analyze_and_execute(
            request=safe_request,
            db=session,
        )

        return response.model_dump(mode="json")

    service = JournaledSchedulerCycleService(
        cycle_service=SafeSchedulerCycleService(
            execute_callback=execute_callback,
        ),
        repository=SchedulerCycleRepository(
            session
        ),
        state_repository=(
            SchedulerStateRepository(session)
        ),
    )

    return service.run(
        account=account,
        limits=limits,
    )
