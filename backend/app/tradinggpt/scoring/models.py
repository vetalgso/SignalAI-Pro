from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TradeDirection = Literal["LONG", "SHORT", "NEUTRAL"]


@dataclass(frozen=True, slots=True)
class ScoringResult:
    # Backward-compatible directional score:
    # 0 = strong short, 50 = neutral, 100 = strong long.
    score: float

    # Strength of the opportunity regardless of direction.
    opportunity_score: float

    confidence: int
    trade_direction: TradeDirection

    signal_score: float
    forecast_score: float
    news_score: float
