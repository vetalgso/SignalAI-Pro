from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ConvictionLevel = Literal[
    "LOW",
    "MEDIUM",
    "HIGH",
    "VERY_HIGH",
]

Recommendation = Literal[
    "AVOID",
    "REDUCE",
    "HOLD",
    "BUY",
    "STRONG_BUY",
]


@dataclass(frozen=True, slots=True)
class ConvictionFactors:
    signal_score: float
    market_score: float
    portfolio_score: float
    quality_score: float


@dataclass(frozen=True, slots=True)
class ConvictionResult:
    score: float
    level: ConvictionLevel
    recommendation: Recommendation
    confidence: float
    position_multiplier: float
    factors: ConvictionFactors
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "score": round(self.score, 2),
            "level": self.level,
            "recommendation": self.recommendation,
            "confidence": round(self.confidence, 4),
            "position_multiplier": round(
                self.position_multiplier,
                2,
            ),
            "factors": {
                "signal_score": round(
                    self.factors.signal_score,
                    2,
                ),
                "market_score": round(
                    self.factors.market_score,
                    2,
                ),
                "portfolio_score": round(
                    self.factors.portfolio_score,
                    2,
                ),
                "quality_score": round(
                    self.factors.quality_score,
                    2,
                ),
            },
            "reasons": list(self.reasons),
        }
