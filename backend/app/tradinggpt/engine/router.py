from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.tradinggpt.exchanges import (
    create_order_execution_service,
    create_portfolio_sync_service,
)
from app.tradinggpt.facade import tradinggpt
from app.tradinggpt.orders.journal_service import (
    JournaledOrderService,
)
from app.tradinggpt.orders.repository import (
    TradingOrderRepository,
)
from app.tradinggpt.positions.repository import (
    TradingPositionRepository,
)

from .execution_service import (
    AnalyzeAndExecuteService,
)
from .models import TradingGPTAnalysisResult
from .schemas import (
    TradingGPTAnalyzeAndExecuteRequest,
    TradingGPTAnalyzeAndExecuteResponse,
    TradingGPTAnalyzeRequest,
    TradingGPTAnalyzeResponse,
)


router = APIRouter(
    prefix="/engine",
    tags=["TradingGPT Engine"],
)


def _run_analysis(
    request: TradingGPTAnalyzeRequest,
) -> TradingGPTAnalysisResult:
    return tradinggpt.analyze(
        scoring_result=request.scoring.to_domain(),
        market_regime_result=(
            request.market_regime.to_domain()
        ),
        portfolio_result=request.portfolio.to_domain(),
        execution_context=(
            request.execution.to_domain()
            if request.execution is not None
            else None
        ),
        account_risk_context=(
            request.account_risk.to_domain()
            if request.account_risk is not None
            else None
        ),
        risk_limits=(
            request.risk_limits.to_domain()
            if request.risk_limits is not None
            else None
        ),
        order_routing=(
            request.order_routing.to_domain()
            if request.order_routing is not None
            else None
        ),
    )


@router.post(
    "/analyze",
    response_model=TradingGPTAnalyzeResponse,
)
def analyze(
    request: TradingGPTAnalyzeRequest,
) -> TradingGPTAnalyzeResponse:
    result = _run_analysis(request)

    return TradingGPTAnalyzeResponse.model_validate(
        result.to_dict()
    )


@router.post(
    "/analyze-and-execute",
    response_model=(
        TradingGPTAnalyzeAndExecuteResponse
    ),
)
def analyze_and_execute(
    request: TradingGPTAnalyzeAndExecuteRequest,
    db: Session = Depends(get_db),
) -> TradingGPTAnalyzeAndExecuteResponse:
    analysis = _run_analysis(request)

    execution_service = (
        create_order_execution_service()
    )
    portfolio_sync_service = (
        create_portfolio_sync_service()
    )
    journal_service = JournaledOrderService(
        repository=TradingOrderRepository(db),
        execution_service=execution_service,
        portfolio_sync_service=(
            portfolio_sync_service
        ),
        position_repository=(
            TradingPositionRepository(db)
        ),
    )
    pipeline_service = AnalyzeAndExecuteService(
        journal_service=journal_service,
    )

    try:
        result = pipeline_service.execute(
            analysis=analysis,
            dry_run=request.dry_run,
            idempotency_key=(
                request.idempotency_key
            ),
        )
    except Exception:
        db.rollback()
        raise

    return (
        TradingGPTAnalyzeAndExecuteResponse
        .model_validate(result)
    )
