from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


PortfolioAction = Literal[
    "ADD",
    "HOLD",
    "REDUCE",
    "AVOID",
]

TradeAction = Literal[
    "BUY",
    "SELL",
    "HOLD",
    "EXIT",
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
class RebalanceTrade:
    asset: str
    action: TradeAction
    current_percent: float
    target_percent: float
    delta_percent: float
    current_amount: float | None
    target_amount: float | None
    trade_amount: float | None
    currency: str
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
    trades: list[RebalanceTrade]
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
            "trades": [
                {
                    "asset": trade.asset,
                    "action": trade.action,
                    "current_percent": round(
                        trade.current_percent,
                        2,
                    ),
                    "target_percent": round(
                        trade.target_percent,
                        2,
                    ),
                    "delta_percent": round(
                        trade.delta_percent,
                        2,
                    ),
                    "current_amount": trade.current_amount,
                    "target_amount": trade.target_amount,
                    "trade_amount": trade.trade_amount,
                    "currency": trade.currency,
                    "reason": trade.reason,
                }
                for trade in self.trades
            ],
            "warnings": self.warnings,
        }
