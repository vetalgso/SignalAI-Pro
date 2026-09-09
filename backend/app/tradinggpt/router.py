from fastapi import APIRouter

from app.tradinggpt.facade import tradinggpt
from app.tradinggpt.schemas import (
    AssistantChatRequest,
    AssistantChatResponse,
    MarketScanRequest,
    MarketScanResponse,
)


router = APIRouter(
    prefix="/assistant",
    tags=["TradingGPT Assistant"],
)


@router.post(
    "/chat",
    response_model=AssistantChatResponse,
)
async def assistant_chat(
    request: AssistantChatRequest,
) -> AssistantChatResponse:
    return await tradinggpt.chat(request)


@router.post(
    "/market-scan",
    response_model=MarketScanResponse,
)
async def market_scan(
    request: MarketScanRequest,
) -> MarketScanResponse:
    result = await tradinggpt.scan_market(
        assets=request.assets or None,
        risk_level=request.risk_level,
        limit=request.limit,
    )

    return MarketScanResponse.model_validate(result)
