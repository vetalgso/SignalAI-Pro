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
    )

    return TradingGPTAnalyzeResponse.model_validate(
        result.to_dict()
    )
