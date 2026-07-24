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
    details: dict = Field(default_factory=dict)
    disclaimer: str


class MarketScanRequest(BaseModel):
    assets: list[str] = Field(
        default_factory=list,
        max_length=20,
    )
    risk_level: Literal["low", "medium", "high"] = "medium"
    limit: int = Field(default=5, ge=1, le=20)


class MarketScanAsset(BaseModel):
    asset: str
    symbol: str
    score: float
    opportunity_score: float
    consensus_score: float = Field(ge=0, le=100)
    timeframe_consensus_score: float = Field(ge=0, le=100)
    ranking_score: float = Field(ge=0, le=100)
    confidence: int
    risk: str
    recommendation: str
    trade_direction: Literal["LONG", "SHORT", "NEUTRAL"]
    signal_action: str | None = None
    forecast_direction: str | None = None
    timeframe_directions: dict[str, str] = Field(
        default_factory=dict
    )
    trend_direction: Literal["LONG", "SHORT", "NEUTRAL"]
    trade_style: Literal[
        "TREND_FOLLOWING",
        "COUNTER_TREND",
        "MIXED",
        "NEUTRAL",
    ]
    reasons: list[str] = Field(default_factory=list)
    quality_penalty: int
    warnings: list[str] = Field(default_factory=list)


class MarketScanResponse(BaseModel):
    scanned_assets: int
    successful_assets: int
    failed_assets: int
    opportunities: list[MarketScanAsset]
    watchlist: list[MarketScanAsset]
    avoid: list[MarketScanAsset]
    ranking: list[MarketScanAsset]
    errors: list[dict[str, str]]
