from fastapi import APIRouter

from app.tradinggpt.orchestrator import TradingGPTOrchestrator
from app.tradinggpt.schemas import AssistantChatRequest, AssistantChatResponse


router = APIRouter(prefix="/assistant", tags=["TradingGPT Assistant"])
orchestrator = TradingGPTOrchestrator()


@router.post("/chat", response_model=AssistantChatResponse)
async def assistant_chat(
    request: AssistantChatRequest,
) -> AssistantChatResponse:
    return await orchestrator.chat(request)
