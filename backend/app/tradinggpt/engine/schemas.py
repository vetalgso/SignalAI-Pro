from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.tradinggpt.market_regime.models import (
    AssetRegimeSignal,
    MarketRegimeResult,
)
from app.tradinggpt.portfolio.models import (
    PortfolioPosition,
    PortfolioResult,
    RebalanceTrade,
)
from app.tradinggpt.scoring.models import ScoringResult


class ScoringResultRequest(BaseModel):
    score: float
    opportunity_score: float
    consensus_score: float
    confidence: int = Field(ge=0, le=100)
    trade_direction: Literal["LONG", "SHORT", "NEUTRAL"]
    signal_score: float
    forecast_score: float
    news_score: float

    def to_domain(self) -> ScoringResult:
        return ScoringResult(**self.model_dump())


class AssetRegimeSignalRequest(BaseModel):
    asset: str
    role: Literal["risk", "defensive", "neutral"]
    signal: Literal["UP", "DOWN", "FLAT"]
    directional_score: float
    volatility_score: float
    weight: float

    def to_domain(self) -> AssetRegimeSignal:
        return AssetRegimeSignal(**self.model_dump())


class MarketRegimeResultRequest(BaseModel):
    market_regime: Literal[
        "RISK_ON",
        "RISK_OFF",
        "BULL",
        "BEAR",
        "SIDEWAYS",
        "HIGH_VOLATILITY",
    ]
    confidence: float
    trend_regime: Literal["BULL", "BEAR", "SIDEWAYS"]
    risk_environment: Literal["RISK_ON", "RISK_OFF", "NEUTRAL"]
    risk_asset_score: float
    defensive_asset_score: float
    risk_appetite_score: float
    market_breadth_score: float
    volatility_score: float
    signals: list[AssetRegimeSignalRequest] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def to_domain(self) -> MarketRegimeResult:
        return MarketRegimeResult(
            market_regime=self.market_regime,
            confidence=self.confidence,
            trend_regime=self.trend_regime,
            risk_environment=self.risk_environment,
            risk_asset_score=self.risk_asset_score,
            defensive_asset_score=self.defensive_asset_score,
            risk_appetite_score=self.risk_appetite_score,
            market_breadth_score=self.market_breadth_score,
            volatility_score=self.volatility_score,
            signals=tuple(item.to_domain() for item in self.signals),
            reasons=tuple(self.reasons),
            warnings=tuple(self.warnings),
        )


class PortfolioPositionRequest(BaseModel):
    asset: str
    target_percent: float
    amount: float | None = None
    action: Literal["ADD", "HOLD", "REDUCE", "AVOID"]
    risk_score: float
    reason: str

    def to_domain(self) -> PortfolioPosition:
        return PortfolioPosition(**self.model_dump())


class RebalanceTradeRequest(BaseModel):
    asset: str
    action: Literal["BUY", "SELL", "HOLD", "EXIT"]
    current_percent: float
    target_percent: float
    delta_percent: float
    current_amount: float | None = None
    target_amount: float | None = None
    trade_amount: float | None = None
    estimated_fee: float | None = None
    net_cash_flow: float | None = None
    currency: str
    reason: str

    def to_domain(self) -> RebalanceTrade:
        return RebalanceTrade(**self.model_dump())


class PortfolioResultRequest(BaseModel):
    capital: float | None = None
    currency: str
    risk_level: Literal["low", "medium", "high"]
    max_position_percent: float
    max_risk_per_trade_percent: float
    portfolio_risk_score: float
    cash_reserve_percent: float
    invested_percent: float
    positions: list[PortfolioPositionRequest] = Field(default_factory=list)
    trades: list[RebalanceTradeRequest] = Field(default_factory=list)
    min_trade_amount: float
    trading_fee_percent: float
    rebalance_tolerance_percent: float
    trade_rounding_amount: float
    estimated_total_fees: float
    warnings: list[str] = Field(default_factory=list)

    def to_domain(self) -> PortfolioResult:
        return PortfolioResult(
            capital=self.capital,
            currency=self.currency,
            risk_level=self.risk_level,
            max_position_percent=self.max_position_percent,
            max_risk_per_trade_percent=self.max_risk_per_trade_percent,
            portfolio_risk_score=self.portfolio_risk_score,
            cash_reserve_percent=self.cash_reserve_percent,
            invested_percent=self.invested_percent,
            positions=[item.to_domain() for item in self.positions],
            trades=[item.to_domain() for item in self.trades],
            min_trade_amount=self.min_trade_amount,
            trading_fee_percent=self.trading_fee_percent,
            rebalance_tolerance_percent=self.rebalance_tolerance_percent,
            trade_rounding_amount=self.trade_rounding_amount,
            estimated_total_fees=self.estimated_total_fees,
            warnings=list(self.warnings),
        )


class TradingGPTAnalyzeRequest(BaseModel):
    scoring: ScoringResultRequest
    market_regime: MarketRegimeResultRequest
    portfolio: PortfolioResultRequest


class TradingGPTAnalyzeResponse(BaseModel):
    scoring: dict[str, object]
    market_regime: dict[str, object]
    portfolio: dict[str, object]
    conviction: dict[str, object]
    explanation: dict[str, object]
