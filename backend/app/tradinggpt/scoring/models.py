from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScoringResult:
    score: float
    confidence: int

    signal_score: float
    forecast_score: float
    news_score: float
