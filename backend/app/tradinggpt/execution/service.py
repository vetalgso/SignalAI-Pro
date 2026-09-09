from __future__ import annotations

import math

from app.tradinggpt.conviction.models import (
    ConvictionResult,
)
from app.tradinggpt.portfolio.models import PortfolioResult

from .models import (
    ExecutionPlan,
    MarketExecutionContext,
)


class ExecutionPlanner:
    """
    Build a deterministic, risk-constrained trade plan.

    Position sizing is based on the monetary loss between entry
    and stop loss. The resulting position is additionally capped
    by the portfolio maximum-position limit.
    """

    TRADE_RECOMMENDATIONS = {
        "BUY",
        "STRONG_BUY",
    }

    @classmethod
    def build(
        cls,
        *,
        conviction: ConvictionResult,
        portfolio: PortfolioResult,
        market: MarketExecutionContext,
    ) -> ExecutionPlan:
        cls._validate_market_context(market)

        if (
            conviction.recommendation
            not in cls.TRADE_RECOMMENDATIONS
        ):
            return cls._build_skip_plan(
                conviction=conviction,
                market=market,
                reason=(
                    "Conviction recommendation does not "
                    "authorize a new long position."
                ),
            )

        if portfolio.capital is None:
            return cls._build_skip_plan(
                conviction=conviction,
                market=market,
                reason=(
                    "Portfolio capital is required for "
                    "position sizing."
                ),
            )

        if portfolio.capital <= 0:
            return cls._build_skip_plan(
                conviction=conviction,
                market=market,
                reason=(
                    "Portfolio capital must be greater "
                    "than zero."
                ),
            )

        entry_price = cls._floor_to_step(
            market.current_price,
            market.price_tick,
        )

        atr_stop_distance = (
            market.atr * market.stop_atr_multiplier
        )

        minimum_stop_distance = (
            entry_price
            * market.minimum_stop_percent
            / 100
        )

        stop_distance = max(
            atr_stop_distance,
            minimum_stop_distance,
        )

        stop_loss = cls._floor_to_step(
            entry_price - stop_distance,
            market.price_tick,
        )

        if stop_loss <= 0:
            return cls._build_skip_plan(
                conviction=conviction,
                market=market,
                reason=(
                    "Calculated stop loss is not a valid "
                    "positive price."
                ),
            )

        effective_stop_distance = (
            entry_price - stop_loss
        )

        take_profit_1 = cls._floor_to_step(
            entry_price
            + effective_stop_distance
            * market.take_profit_1_rr,
            market.price_tick,
        )

        take_profit_2 = cls._floor_to_step(
            entry_price
            + effective_stop_distance
            * market.take_profit_2_rr,
            market.price_tick,
        )

        base_risk_budget = (
            portfolio.capital
            * portfolio.max_risk_per_trade_percent
            / 100
        )

        risk_budget = (
            base_risk_budget
            * conviction.position_multiplier
        )

        raw_quantity = (
            risk_budget / effective_stop_distance
        )

        maximum_position_value = (
            portfolio.capital
            * portfolio.max_position_percent
            / 100
        )

        raw_position_value = (
            raw_quantity * entry_price
        )

        position_cap_applied = (
            raw_position_value
            > maximum_position_value
        )

        if position_cap_applied:
            raw_quantity = (
                maximum_position_value / entry_price
            )

        position_quantity = cls._floor_to_step(
            raw_quantity,
            market.quantity_step,
        )

        position_value = (
            position_quantity * entry_price
        )

        actual_risk_amount = (
            position_quantity
            * effective_stop_distance
        )

        actual_risk_percent = (
            actual_risk_amount
            / portfolio.capital
            * 100
        )

        warnings: list[str] = []

        if position_cap_applied:
            warnings.append(
                "Position size was reduced by the "
                "portfolio maximum-position limit."
            )

        if (
            position_value
            < portfolio.min_trade_amount
        ):
            return cls._build_skip_plan(
                conviction=conviction,
                market=market,
                reason=(
                    "Calculated position value is below "
                    "the portfolio minimum trade amount."
                ),
                risk_budget=risk_budget,
                warning=(
                    f"Calculated position value "
                    f"{position_value:.2f} "
                    f"{portfolio.currency} is below "
                    f"{portfolio.min_trade_amount:.2f}."
                ),
            )

        return ExecutionPlan(
            status="READY",
            symbol=market.symbol.upper(),
            side="LONG",
            recommendation=(
                conviction.recommendation
            ),
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            stop_distance=effective_stop_distance,
            stop_distance_percent=(
                effective_stop_distance
                / entry_price
                * 100
            ),
            risk_reward_1=(
                market.take_profit_1_rr
            ),
            risk_reward_2=(
                market.take_profit_2_rr
            ),
            risk_budget=risk_budget,
            position_quantity=position_quantity,
            position_value=position_value,
            actual_risk_amount=actual_risk_amount,
            actual_risk_percent=actual_risk_percent,
            position_cap_applied=(
                position_cap_applied
            ),
            reasons=(
                (
                    f"{conviction.recommendation} "
                    f"recommendation with "
                    f"{conviction.level} conviction."
                ),
                (
                    "Position size is constrained by "
                    "stop-loss risk and portfolio limits."
                ),
            ),
            warnings=tuple(warnings),
        )

    @staticmethod
    def _build_skip_plan(
        *,
        conviction: ConvictionResult,
        market: MarketExecutionContext,
        reason: str,
        risk_budget: float = 0.0,
        warning: str | None = None,
    ) -> ExecutionPlan:
        warnings = (
            (warning,)
            if warning is not None
            else ()
        )

        return ExecutionPlan(
            status="SKIP",
            symbol=market.symbol.upper(),
            side="NONE",
            recommendation=(
                conviction.recommendation
            ),
            entry_price=None,
            stop_loss=None,
            take_profit_1=None,
            take_profit_2=None,
            stop_distance=None,
            stop_distance_percent=None,
            risk_reward_1=None,
            risk_reward_2=None,
            risk_budget=risk_budget,
            position_quantity=0.0,
            position_value=0.0,
            actual_risk_amount=0.0,
            actual_risk_percent=0.0,
            position_cap_applied=False,
            reasons=(reason,),
            warnings=warnings,
        )

    @staticmethod
    def _validate_market_context(
        market: MarketExecutionContext,
    ) -> None:
        positive_values = {
            "current_price": market.current_price,
            "atr": market.atr,
            "quantity_step": market.quantity_step,
            "price_tick": market.price_tick,
            "stop_atr_multiplier": (
                market.stop_atr_multiplier
            ),
            "take_profit_1_rr": (
                market.take_profit_1_rr
            ),
            "take_profit_2_rr": (
                market.take_profit_2_rr
            ),
            "minimum_stop_percent": (
                market.minimum_stop_percent
            ),
        }

        for name, value in positive_values.items():
            if not math.isfinite(value) or value <= 0:
                raise ValueError(
                    f"{name} must be a finite positive "
                    "number."
                )

        if (
            market.take_profit_2_rr
            <= market.take_profit_1_rr
        ):
            raise ValueError(
                "take_profit_2_rr must be greater than "
                "take_profit_1_rr."
            )

        if not market.symbol.strip():
            raise ValueError(
                "symbol must not be empty."
            )

    @staticmethod
    def _floor_to_step(
        value: float,
        step: float,
    ) -> float:
        units = math.floor(
            (value / step) + 1e-12
        )

        return round(
            units * step,
            12,
        )
