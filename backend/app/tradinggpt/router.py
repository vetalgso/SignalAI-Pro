from fastapi import APIRouter

from app.tradinggpt.modules.crypto_asset import CryptoAssetAnalysisModule
from app.tradinggpt.modules.market_scanner import CryptoMarketScanner
from app.tradinggpt.orchestrator import TradingGPTOrchestrator
from app.tradinggpt.schemas import (
    AssistantChatRequest,
    AssistantChatResponse,
    MarketScanRequest,
    MarketScanResponse,
)


router = APIRouter(prefix="/assistant", tags=["TradingGPT Assistant"])
orchestrator = TradingGPTOrchestrator()
market_scanner = CryptoMarketScanner(CryptoAssetAnalysisModule())


@router.post("/chat", response_model=AssistantChatResponse)
async def assistant_chat(
    request: AssistantChatRequest,
) -> AssistantChatResponse:
    return await orchestrator.chat(request)



@router.post("/market-scan", response_model=MarketScanResponse)
async def market_scan(
    request: MarketScanRequest,
) -> MarketScanResponse:
    result = await market_scanner.scan(
        assets=request.assets or None,
        risk_level=request.risk_level,
        limit=request.limit,
    )
    return MarketScanResponse.model_validate(result)
