from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


MarketRegime = Literal[
    "RISK_ON",
    "RISK_OFF",
    "BULL",
    "BEAR",
    "SIDEWAYS",
    "HIGH_VOLATILITY",
]

MarketTrend = Literal[
    "BULL",
    "BEAR",
    "SIDEWAYS",
]

RiskEnvironment = Literal[
    "RISK_ON",
    "RISK_OFF",
    "NEUTRAL",
]

AssetSignal = Literal[
    "UP",
    "DOWN",
    "FLAT",
]

AssetRole = Literal[
    "risk",
    "defensive",
    "neutral",
]


@dataclass(frozen=True, slots=True)
class MarketObservation:
    asset: str
    trend_score: float
    momentum_score: float
    volatility_score: float
    weight: float | None = None

    def __post_init__(self) -> None:
        asset = self.asset.strip().upper()

        if not asset:
            raise ValueError("asset must not be empty")

        if not -100 <= self.trend_score <= 100:
            raise ValueError(
                "trend_score must be between -100 and 100"
            )

        if not -100 <= self.momentum_score <= 100:
            raise ValueError(
                "momentum_score must be between -100 and 100"
            )

        if not 0 <= self.volatility_score <= 100:
            raise ValueError(
                "volatility_score must be between 0 and 100"
            )

        if self.weight is not None and self.weight <= 0:
            raise ValueError("weight must be greater than zero")

        object.__setattr__(self, "asset", asset)


@dataclass(frozen=True, slots=True)
class AssetRegimeSignal:
    asset: str
    role: AssetRole
    signal: AssetSignal
    directional_score: float
    volatility_score: float
    weight: float

    def to_dict(self) -> dict[str, object]:
        return {
            "asset": self.asset,
            "role": self.role,
            "signal": self.signal,
            "directional_score": round(
                self.directional_score,
                2,
            ),
            "volatility_score": round(
                self.volatility_score,
                2,
            ),
            "weight": round(self.weight, 2),
        }


@dataclass(frozen=True, slots=True)
class MarketRegimeResult:
    market_regime: MarketRegime
    confidence: float
    trend_regime: MarketTrend
    risk_environment: RiskEnvironment
    risk_asset_score: float
    defensive_asset_score: float
    risk_appetite_score: float
    market_breadth_score: float
    volatility_score: float
    signals: tuple[AssetRegimeSignal, ...]
    reasons: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "market_regime": self.market_regime,
            "confidence": round(self.confidence, 4),
            "trend_regime": self.trend_regime,
            "risk_environment": self.risk_environment,
            "risk_asset_score": round(
                self.risk_asset_score,
                2,
            ),
            "defensive_asset_score": round(
                self.defensive_asset_score,
                2,
            ),
            "risk_appetite_score": round(
                self.risk_appetite_score,
                2,
            ),
            "market_breadth_score": round(
                self.market_breadth_score,
                4,
            ),
            "volatility_score": round(
                self.volatility_score,
                2,
            ),
            "signals": {
                signal.asset: signal.signal
                for signal in self.signals
            },
            "signal_details": [
                signal.to_dict()
                for signal in self.signals
            ],
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
        }
