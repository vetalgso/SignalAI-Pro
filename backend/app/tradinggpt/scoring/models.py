from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TradeDirection = Literal["LONG", "SHORT", "NEUTRAL"]


@dataclass(frozen=True, slots=True)
class ScoringResult:
    # Directional score:
    # 0 = strong short, 50 = neutral, 100 = strong long.
    score: float

    # Strength of the trade opportunity regardless of direction.
    opportunity_score: float

    # Agreement between the available analytical sources.
    # 0 = strong conflict, 50 = mixed/neutral, 100 = strong agreement.
    consensus_score: float

    confidence: int
    trade_direction: TradeDirection

    signal_score: float
    forecast_score: float
    news_score: float
