from __future__ import annotations

from fastapi import APIRouter

from app.tradinggpt.facade import tradinggpt

from .schemas import (
    TradingGPTAnalyzeRequest,
    TradingGPTAnalyzeResponse,
)


router = APIRouter(
    prefix="/engine",
    tags=["TradingGPT Engine"],
)


@router.post(
    "/analyze",
    response_model=TradingGPTAnalyzeResponse,
)
def analyze(
    request: TradingGPTAnalyzeRequest,
) -> TradingGPTAnalyzeResponse:
    result = tradinggpt.analyze(
        scoring_result=request.scoring.to_domain(),
        market_regime_result=request.market_regime.to_domain(),
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

    return TradingGPTAnalyzeResponse.model_validate(
        result.to_dict()
    )
