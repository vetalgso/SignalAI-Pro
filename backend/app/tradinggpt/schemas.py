from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=10,
    )
    risk_level: RiskLevel = "medium"
    investment_horizon: InvestmentHorizon = "medium"
    preferred_markets: list[str] = Field(
        default_factory=list
    )
    existing_assets: list[str] = Field(
        default_factory=list
    )
    current_allocations: dict[str, float] = Field(
        default_factory=dict
    )
    max_position_percent: float = Field(
        default=25,
        gt=0,
        le=100,
    )
    leverage_allowed: bool = False

    @field_validator(
        "existing_assets",
        mode="before",
    )
    @classmethod
    def normalize_existing_assets(
        cls,
        value: object,
    ) -> object:
        if value is None:
            return []

        if not isinstance(value, list):
            return value

        normalized: list[str] = []
        seen: set[str] = set()

        for raw_asset in value:
            asset = str(raw_asset).strip()

            if not asset:
                continue

            key = asset.casefold()

            if key in seen:
                continue

            seen.add(key)
            normalized.append(asset)

        return normalized

    @field_validator(
        "current_allocations",
        mode="before",
    )
    @classmethod
    def normalize_current_allocations(
        cls,
        value: object,
    ) -> object:
        if value is None:
            return {}

        if not isinstance(value, dict):
            return value

        normalized: dict[str, float] = {}

        for raw_asset, raw_percent in value.items():
            asset = str(raw_asset).strip()

            if not asset:
                raise ValueError(
                    "Asset name cannot be empty"
                )

            normalized[asset] = raw_percent

        return normalized

    @field_validator("current_allocations")
    @classmethod
    def validate_current_allocations(
        cls,
        allocations: dict[str, float],
    ) -> dict[str, float]:
        for asset, percent in allocations.items():
            if percent < 0:
                raise ValueError(
                    f"Allocation for {asset} cannot "
                    "be negative"
                )

            if percent > 100:
                raise ValueError(
                    f"Allocation for {asset} cannot "
                    "exceed 100 percent"
                )

        total = sum(allocations.values())

        if total > 100.000001:
            raise ValueError(
                "Current allocations cannot exceed "
                "100 percent in total"
            )

        return allocations

    @model_validator(mode="after")
    def synchronize_existing_assets(
        self,
    ) -> "InvestorContext":
        known = {
            asset.casefold()
            for asset in self.existing_assets
        }

        for asset in self.current_allocations:
            if asset.casefold() not in known:
                self.existing_assets.append(asset)
                known.add(asset.casefold())

        return self


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
