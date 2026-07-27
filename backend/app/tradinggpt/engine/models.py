from __future__ import annotations

from dataclasses import dataclass

from app.tradinggpt.explanation import TradingExplanation
from app.tradinggpt.pipeline import TradingPipelineResult


@dataclass(frozen=True, slots=True)
class TradingGPTAnalysisResult:
    pipeline: TradingPipelineResult
    explanation: TradingExplanation

    @property
    def scoring(self):
        return self.pipeline.scoring

    @property
    def market_regime(self):
        return self.pipeline.market_regime

    @property
    def portfolio(self):
        return self.pipeline.portfolio

    @property
    def conviction(self):
        return self.pipeline.conviction

    def to_dict(self) -> dict[str, object]:
        payload = self.pipeline.to_dict()
        payload["explanation"] = self.explanation.to_dict()
        return payload
