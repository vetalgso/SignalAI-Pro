from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.indicators import IndicatorResponse
from app.schemas.signal import SignalRead


class TradeLevels(BaseModel):
    entry: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    risk_reward_ratio: float


class ScoreBreakdown(BaseModel):
    long_score: int = Field(ge=0, le=100)
    short_score: int = Field(ge=0, le=100)
    threshold: int = Field(ge=0, le=100)


class SignalAnalysisResponse(BaseModel):
    symbol: str
    interval: str
    action: Literal["LONG", "SHORT", "WAIT"]
    confidence: float = Field(ge=0, le=100)
    strategy: str
    score: ScoreBreakdown
    levels: TradeLevels | None
    reasons: list[str]
    warnings: list[str]
    indicators: IndicatorResponse


class GeneratedSignalResponse(BaseModel):
    analysis: SignalAnalysisResponse
    saved_signal: SignalRead
