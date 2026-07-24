from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["low", "medium", "high"]
InvestmentHorizon = Literal["short", "medium", "long"]
AssistantIntent = Literal[
    "market_analysis",
    "asset_analysis",
    "portfolio_allocation",
    "daily_opportunities",
    "overnight_report",
    "risk_analysis",
    "general",
]


class InvestorContext(BaseModel):
    capital: float | None = Field(default=None, gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=10)
    risk_level: RiskLevel = "medium"
    investment_horizon: InvestmentHorizon = "medium"
    preferred_markets: list[str] = Field(default_factory=list)
    existing_assets: list[str] = Field(default_factory=list)
    max_position_percent: float = Field(default=25, gt=0, le=100)
    leverage_allowed: bool = False


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)
    context: InvestorContext = Field(default_factory=InvestorContext)


class AnalysisFactor(BaseModel):
    type: str
    score: int = Field(ge=0, le=100)
    summary: str


class PortfolioAllocationItem(BaseModel):
    asset: str
    allocation_percent: float = Field(ge=0, le=100)
    amount: float | None = None
    reason: str


class AssistantChatResponse(BaseModel):
    intent: AssistantIntent
    answer: str
    confidence: int = Field(ge=0, le=100)
    risk: RiskLevel
    market_view: Literal["bullish", "bearish", "neutral", "mixed"]
    factors: list[AnalysisFactor] = Field(default_factory=list)
    portfolio: list[PortfolioAllocationItem] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    disclaimer: str
