from __future__ import annotations

from app.tradinggpt.conviction import (
    ConvictionAdapter,
    ConvictionEngine,
)
from app.tradinggpt.market_regime.models import MarketRegimeResult
from app.tradinggpt.portfolio.models import PortfolioResult
from app.tradinggpt.scoring.models import ScoringResult

from .models import TradingPipelineResult


class TradingPipeline:
    """Combine TradingGPT engine results into one decision result."""

    @classmethod
    def run(
        cls,
        *,
        scoring_result: ScoringResult,
        market_regime_result: MarketRegimeResult,
        portfolio_result: PortfolioResult,
    ) -> TradingPipelineResult:
        factors = ConvictionAdapter.from_results(
            scoring_result=scoring_result,
            market_regime_result=market_regime_result,
            portfolio_result=portfolio_result,
        )

        conviction_result = ConvictionEngine.calculate(
            factors=factors,
        )

        return TradingPipelineResult(
            scoring=scoring_result,
            market_regime=market_regime_result,
            portfolio=portfolio_result,
            conviction=conviction_result,
        )
