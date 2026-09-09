from __future__ import annotations

from app.tradinggpt.market_regime.models import MarketRegimeResult
from app.tradinggpt.portfolio.models import PortfolioResult
from app.tradinggpt.scoring.models import ScoringResult

from .models import ConvictionFactors


class ConvictionAdapter:
    """Convert results from TradingGPT engines into conviction factors."""

    @classmethod
    def from_results(
        cls,
        *,
        scoring_result: ScoringResult,
        market_regime_result: MarketRegimeResult,
        portfolio_result: PortfolioResult,
    ) -> ConvictionFactors:
        return ConvictionFactors(
            signal_score=cls._clamp_score(
                scoring_result.signal_score
            ),
            market_score=cls._clamp_score(
                market_regime_result.risk_appetite_score
            ),
            portfolio_score=cls._portfolio_score(
                portfolio_result
            ),
            quality_score=cls._quality_score(
                scoring_result
            ),
        )

    @staticmethod
    def _portfolio_score(
        portfolio_result: PortfolioResult,
    ) -> float:
        """
        Convert portfolio risk into portfolio suitability.

        Low portfolio risk means high suitability:
        risk 0   -> score 100
        risk 100 -> score 0
        """
        return ConvictionAdapter._clamp_score(
            100.0 - portfolio_result.portfolio_risk_score
        )

    @staticmethod
    def _quality_score(
        scoring_result: ScoringResult,
    ) -> float:
        """
        Quality combines source agreement and model confidence.
        """
        quality = (
            scoring_result.consensus_score
            + float(scoring_result.confidence)
        ) / 2.0

        return ConvictionAdapter._clamp_score(quality)

    @staticmethod
    def _clamp_score(value: float) -> float:
        return round(
            max(0.0, min(100.0, float(value))),
            2,
        )
