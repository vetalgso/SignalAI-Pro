from __future__ import annotations

from app.tradinggpt.conviction.models import (
    ConvictionFactors,
    ConvictionResult,
)


class ConvictionEngine:
    SIGNAL_WEIGHT = 0.35
    MARKET_WEIGHT = 0.30
    PORTFOLIO_WEIGHT = 0.20
    QUALITY_WEIGHT = 0.15

    @classmethod
    def calculate(
        cls,
        *,
        factors: ConvictionFactors,
    ) -> ConvictionResult:
        score = (
            factors.signal_score * cls.SIGNAL_WEIGHT
            + factors.market_score * cls.MARKET_WEIGHT
            + factors.portfolio_score * cls.PORTFOLIO_WEIGHT
            + factors.quality_score * cls.QUALITY_WEIGHT
        )

        score = max(0.0, min(score, 100.0))

        if score >= 85:
            level = "VERY_HIGH"
            recommendation = "STRONG_BUY"
            multiplier = 1.50
        elif score >= 70:
            level = "HIGH"
            recommendation = "BUY"
            multiplier = 1.25
        elif score >= 50:
            level = "MEDIUM"
            recommendation = "HOLD"
            multiplier = 1.00
        elif score >= 30:
            level = "LOW"
            recommendation = "REDUCE"
            multiplier = 0.50
        else:
            level = "LOW"
            recommendation = "AVOID"
            multiplier = 0.25

        confidence = score / 100.0

        reasons = (
            f"Signal score: {factors.signal_score:.1f}",
            f"Market score: {factors.market_score:.1f}",
            f"Portfolio score: {factors.portfolio_score:.1f}",
            f"Quality score: {factors.quality_score:.1f}",
        )

        return ConvictionResult(
            score=score,
            level=level,
            recommendation=recommendation,
            confidence=confidence,
            position_multiplier=multiplier,
            factors=factors,
            reasons=reasons,
        )
