from __future__ import annotations

from dataclasses import dataclass

from app.tradinggpt.conviction.models import ConvictionResult
from app.tradinggpt.market_regime.models import MarketRegimeResult
from app.tradinggpt.portfolio.models import PortfolioResult
from app.tradinggpt.scoring.models import ScoringResult


@dataclass(frozen=True, slots=True)
class TradingPipelineResult:
    scoring: ScoringResult
    market_regime: MarketRegimeResult
    portfolio: PortfolioResult
    conviction: ConvictionResult

    def to_dict(self) -> dict[str, object]:
        return {
            "scoring": {
                "score": round(self.scoring.score, 2),
                "opportunity_score": round(
                    self.scoring.opportunity_score,
                    2,
                ),
                "consensus_score": round(
                    self.scoring.consensus_score,
                    2,
                ),
                "confidence": self.scoring.confidence,
                "trade_direction": (
                    self.scoring.trade_direction
                ),
                "signal_score": round(
                    self.scoring.signal_score,
                    2,
                ),
                "forecast_score": round(
                    self.scoring.forecast_score,
                    2,
                ),
                "news_score": round(
                    self.scoring.news_score,
                    2,
                ),
            },
            "market_regime": self.market_regime.to_dict(),
            "portfolio": self.portfolio.to_dict(),
            "conviction": {
                "score": round(self.conviction.score, 2),
                "level": self.conviction.level,
                "recommendation": (
                    self.conviction.recommendation
                ),
                "confidence": round(
                    self.conviction.confidence,
                    4,
                ),
                "position_multiplier": round(
                    self.conviction.position_multiplier,
                    2,
                ),
                "factors": {
                    "signal_score": round(
                        self.conviction.factors.signal_score,
                        2,
                    ),
                    "market_score": round(
                        self.conviction.factors.market_score,
                        2,
                    ),
                    "portfolio_score": round(
                        self.conviction.factors.portfolio_score,
                        2,
                    ),
                    "quality_score": round(
                        self.conviction.factors.quality_score,
                        2,
                    ),
                },
                "reasons": list(self.conviction.reasons),
            },
        }
