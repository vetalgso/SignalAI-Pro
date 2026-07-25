from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


PortfolioAction = Literal[
    "ADD",
    "HOLD",
    "REDUCE",
    "AVOID",
]

PortfolioRisk = Literal[
    "low",
    "medium",
    "high",
]


@dataclass(frozen=True, slots=True)
class PortfolioPosition:
    asset: str
    target_percent: float
    amount: float | None
    action: PortfolioAction
    risk_score: float
    reason: str


@dataclass(frozen=True, slots=True)
class PortfolioResult:
    capital: float | None
    currency: str
    risk_level: PortfolioRisk
    max_position_percent: float
    max_risk_per_trade_percent: float
    portfolio_risk_score: float
    cash_reserve_percent: float
    invested_percent: float
    positions: list[PortfolioPosition]
    warnings: list[str]

    def to_dict(self) -> dict:
        return {
            "capital": self.capital,
            "currency": self.currency,
            "risk_level": self.risk_level,
            "max_position_percent": round(
                self.max_position_percent,
                2,
            ),
            "max_risk_per_trade_percent": round(
                self.max_risk_per_trade_percent,
                2,
            ),
            "portfolio_risk_score": round(
                self.portfolio_risk_score,
                2,
            ),
            "cash_reserve_percent": round(
                self.cash_reserve_percent,
                2,
            ),
            "invested_percent": round(
                self.invested_percent,
                2,
            ),
            "positions": [
                {
                    "asset": position.asset,
                    "target_percent": round(
                        position.target_percent,
                        2,
                    ),
                    "amount": position.amount,
                    "action": position.action,
                    "risk_score": round(
                        position.risk_score,
                        2,
                    ),
                    "reason": position.reason,
                }
                for position in self.positions
            ],
            "warnings": self.warnings,
        }
