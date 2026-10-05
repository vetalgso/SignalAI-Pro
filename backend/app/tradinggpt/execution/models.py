from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ExecutionPlanStatus = Literal[
    "READY",
    "SKIP",
]

ExecutionSide = Literal[
    "LONG",
    "NONE",
]


@dataclass(frozen=True, slots=True)
class MarketExecutionContext:
    """
    Live market values required to construct an execution plan.

    These values are deliberately kept outside the analytical
    pipeline because they may change immediately before execution.
    """

    symbol: str
    current_price: float
    atr: float
    quantity_step: float = 0.000001
    price_tick: float = 0.01
    stop_atr_multiplier: float = 1.5
    take_profit_1_rr: float = 1.5
    take_profit_2_rr: float = 2.5
    minimum_stop_percent: float = 0.5


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    status: ExecutionPlanStatus
    symbol: str
    side: ExecutionSide
    recommendation: str
    entry_price: float | None
    stop_loss: float | None
    take_profit_1: float | None
    take_profit_2: float | None
    stop_distance: float | None
    stop_distance_percent: float | None
    risk_reward_1: float | None
    risk_reward_2: float | None
    risk_budget: float
    position_quantity: float
    position_value: float
    actual_risk_amount: float
    actual_risk_percent: float
    position_cap_applied: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "symbol": self.symbol,
            "side": self.side,
            "recommendation": self.recommendation,
            "entry_price": self._round_optional(
                self.entry_price,
            ),
            "stop_loss": self._round_optional(
                self.stop_loss,
            ),
            "take_profit_1": self._round_optional(
                self.take_profit_1,
            ),
            "take_profit_2": self._round_optional(
                self.take_profit_2,
            ),
            "stop_distance": self._round_optional(
                self.stop_distance,
            ),
            "stop_distance_percent": (
                self._round_optional(
                    self.stop_distance_percent,
                )
            ),
            "risk_reward_1": self.risk_reward_1,
            "risk_reward_2": self.risk_reward_2,
            "risk_budget": round(self.risk_budget, 2),
            "position_quantity": self.position_quantity,
            "position_value": round(
                self.position_value,
                2,
            ),
            "actual_risk_amount": round(
                self.actual_risk_amount,
                2,
            ),
            "actual_risk_percent": round(
                self.actual_risk_percent,
                4,
            ),
            "position_cap_applied": (
                self.position_cap_applied
            ),
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
        }

    @staticmethod
    def _round_optional(
        value: float | None,
    ) -> float | None:
        if value is None:
            return None

        return round(value, 8)
