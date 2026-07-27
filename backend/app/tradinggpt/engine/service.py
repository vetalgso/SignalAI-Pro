from __future__ import annotations

from app.tradinggpt.execution import (
    ExecutionPlanner,
    MarketExecutionContext,
)
from app.tradinggpt.explanation import TradingExplanationEngine
from app.tradinggpt.market_regime.models import MarketRegimeResult
from app.tradinggpt.pipeline import TradingPipeline
from app.tradinggpt.portfolio.models import PortfolioResult
from app.tradinggpt.scoring.models import ScoringResult
from app.tradinggpt.risk import (
    AccountRiskContext,
    RiskLimits,
    RiskManager,
)

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
        execution_context: MarketExecutionContext | None = None,
        account_risk_context: AccountRiskContext | None = None,
        risk_limits: RiskLimits | None = None,
    ) -> TradingGPTAnalysisResult:
        pipeline = TradingPipeline.run(
            scoring_result=scoring_result,
            market_regime_result=market_regime_result,
            portfolio_result=portfolio_result,
        )

        explanation = TradingExplanationEngine.explain(
            pipeline
        )

        execution_plan = None
        risk_decision = None

        if execution_context is not None:
            execution_plan = ExecutionPlanner.build(
                conviction=pipeline.conviction,
                portfolio=pipeline.portfolio,
                market=execution_context,
            )

        if (
            execution_plan is not None
            and account_risk_context is not None
        ):
            risk_decision = RiskManager.evaluate(
                execution_plan=execution_plan,
                account=account_risk_context,
                limits=risk_limits,
            )

        return TradingGPTAnalysisResult(
            pipeline=pipeline,
            explanation=explanation,
            execution_plan=execution_plan,
            risk_decision=risk_decision,
        )
