from __future__ import annotations

from app.tradinggpt.engine import (
    TradingGPTAnalysisResult,
    TradingGPTEngine,
)
from app.tradinggpt.market_regime.models import MarketRegimeResult
from app.tradinggpt.modules.crypto_asset import (
    CryptoAssetAnalysisModule,
)
from app.tradinggpt.modules.market_scanner import (
    CryptoMarketScanner,
)
from app.tradinggpt.orchestrator import TradingGPTOrchestrator
from app.tradinggpt.portfolio.models import PortfolioResult
from app.tradinggpt.schemas import (
    AssistantChatRequest,
    AssistantChatResponse,
)
from app.tradinggpt.scoring.models import ScoringResult


class TradingGPTFacade:
    """
    Single application-level entry point for TradingGPT.

    The facade coordinates:
    - conversational assistant requests;
    - market scanning;
    - deterministic analytical decisions.

    Domain engines remain independent and reusable.
    """

    def __init__(
        self,
        *,
        orchestrator: TradingGPTOrchestrator | None = None,
        market_scanner: CryptoMarketScanner | None = None,
        engine: TradingGPTEngine | None = None,
    ) -> None:
        self._orchestrator = (
            orchestrator or TradingGPTOrchestrator()
        )
        self._market_scanner = (
            market_scanner
            or CryptoMarketScanner(
                CryptoAssetAnalysisModule()
            )
        )
        self._engine = engine or TradingGPTEngine()

    async def chat(
        self,
        request: AssistantChatRequest,
    ) -> AssistantChatResponse:
        return await self._orchestrator.chat(request)

    async def scan_market(
        self,
        *,
        assets: list[str] | None,
        risk_level: str,
        limit: int,
    ) -> object:
        return await self._market_scanner.scan(
            assets=assets,
            risk_level=risk_level,
            limit=limit,
        )

    def analyze(
        self,
        *,
        scoring_result: ScoringResult,
        market_regime_result: MarketRegimeResult,
        portfolio_result: PortfolioResult,
    ) -> TradingGPTAnalysisResult:
        return self._engine.analyze(
            scoring_result=scoring_result,
            market_regime_result=market_regime_result,
            portfolio_result=portfolio_result,
        )


tradinggpt = TradingGPTFacade()
