from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


RiskDecisionStatus = Literal[
    "ALLOW",
    "REDUCE_SIZE",
    "DENY",
]


@dataclass(frozen=True, slots=True)
class RiskLimits:
    """
    Configurable account-level trading limits.

    All percentage values use the conventional 0-100 scale.
    """

    max_daily_loss_percent: float = 3.0
    max_drawdown_percent: float = 10.0
    max_total_exposure_percent: float = 80.0
    max_correlated_exposure_percent: float = 40.0
    max_open_positions: int = 5
    minimum_position_value: float = 25.0


@dataclass(frozen=True, slots=True)
class AccountRiskContext:
    """
    Current account state used by the Risk Manager.
    """

    equity: float
    peak_equity: float
    daily_pnl: float
    open_positions: int
    current_exposure_value: float
    correlated_exposure_value: float = 0.0


@dataclass(frozen=True, slots=True)
class RiskDecision:
    status: RiskDecisionStatus
    symbol: str
    original_position_quantity: float
    original_position_value: float
    approved_position_quantity: float
    approved_position_value: float
    approved_risk_amount: float
    size_multiplier: float
    daily_loss_percent: float
    drawdown_percent: float
    exposure_percent_before: float
    exposure_percent_after: float
    correlated_exposure_percent_after: float
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.status in {
            "ALLOW",
            "REDUCE_SIZE",
        }

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["allowed"] = self.allowed
        return payload
