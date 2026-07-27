from __future__ import annotations

from app.tradinggpt.explanation import TradingExplanationEngine
from app.tradinggpt.market_regime.models import MarketRegimeResult
from app.tradinggpt.pipeline import TradingPipeline
from app.tradinggpt.portfolio.models import PortfolioResult
from app.tradinggpt.scoring.models import ScoringResult

from .models import TradingGPTAnalysisResult


class TradingGPTEngine:
    """High-level TradingGPT orchestration service."""

    @classmethod
    def analyze(
        cls,
        *,
        scoring_result: ScoringResult,
        market_regime_result: MarketRegimeResult,
        portfolio_result: PortfolioResult,
    ) -> TradingGPTAnalysisResult:
        pipeline = TradingPipeline.run(
            scoring_result=scoring_result,
            market_regime_result=market_regime_result,
            portfolio_result=portfolio_result,
        )

        explanation = TradingExplanationEngine.explain(
            pipeline
        )

        return TradingGPTAnalysisResult(
            pipeline=pipeline,
            explanation=explanation,
        )
