from __future__ import annotations

from app.tradinggpt.conviction.models import ConvictionResult
from app.tradinggpt.execution import ExecutionPlan
from app.tradinggpt.risk import RiskDecision

from .models import FinalTradeDecision


class FinalTradeDecisionEngine:
    """Builds the final deterministic trading decision."""

    @classmethod
    def build(
        cls,
        *,
        conviction: ConvictionResult,
        execution_plan: ExecutionPlan | None,
        risk_decision: RiskDecision | None,
    ) -> FinalTradeDecision:
        if execution_plan is None:
            return cls._no_trade_without_plan(conviction)

        if execution_plan.status != "READY":
            return cls._no_trade_for_skipped_plan(
                conviction=conviction,
                execution_plan=execution_plan,
            )

        if risk_decision is None:
            return cls._no_trade_without_risk(
                conviction=conviction,
                execution_plan=execution_plan,
            )

        if risk_decision.status == "DENY":
            return FinalTradeDecision(
                status="REJECT",
                symbol=execution_plan.symbol,
                side=execution_plan.side,
                recommendation=execution_plan.recommendation,
                approved_quantity=0.0,
                approved_value=0.0,
                approved_risk=0.0,
                conviction_score=conviction.score,
                execution_ready=True,
                risk_allowed=False,
                summary=(
                    f"{execution_plan.recommendation} rejected "
                    "by account risk controls"
                ),
                reasons=risk_decision.reasons,
                warnings=cls._merge_warnings(
                    execution_plan.warnings,
                    risk_decision.warnings,
                ),
            )

        if risk_decision.status == "REDUCE_SIZE":
            return FinalTradeDecision(
                status="EXECUTE_REDUCED",
                symbol=execution_plan.symbol,
                side=execution_plan.side,
                recommendation=execution_plan.recommendation,
                approved_quantity=(
                    risk_decision.approved_position_quantity
                ),
                approved_value=(
                    risk_decision.approved_position_value
                ),
                approved_risk=(
                    risk_decision.approved_risk_amount
                ),
                conviction_score=conviction.score,
                execution_ready=True,
                risk_allowed=True,
                summary=(
                    f"{execution_plan.recommendation} approved "
                    "with reduced position"
                ),
                reasons=risk_decision.reasons,
                warnings=cls._merge_warnings(
                    execution_plan.warnings,
                    risk_decision.warnings,
                ),
            )

        return FinalTradeDecision(
            status="EXECUTE",
            symbol=execution_plan.symbol,
            side=execution_plan.side,
            recommendation=execution_plan.recommendation,
            approved_quantity=(
                risk_decision.approved_position_quantity
            ),
            approved_value=risk_decision.approved_position_value,
            approved_risk=risk_decision.approved_risk_amount,
            conviction_score=conviction.score,
            execution_ready=True,
            risk_allowed=True,
            summary=(
                f"{execution_plan.recommendation} approved "
                "with full position"
            ),
            reasons=risk_decision.reasons,
            warnings=cls._merge_warnings(
                execution_plan.warnings,
                risk_decision.warnings,
            ),
        )

    @staticmethod
    def _no_trade_without_plan(
        conviction: ConvictionResult,
    ) -> FinalTradeDecision:
        return FinalTradeDecision(
            status="NO_TRADE",
            symbol=None,
            side="NONE",
            recommendation=conviction.recommendation,
            approved_quantity=0.0,
            approved_value=0.0,
            approved_risk=0.0,
            conviction_score=conviction.score,
            execution_ready=False,
            risk_allowed=False,
            summary="No execution plan was requested",
            reasons=(
                "Market execution context was not provided.",
            ),
        )

    @classmethod
    def _no_trade_for_skipped_plan(
        cls,
        *,
        conviction: ConvictionResult,
        execution_plan: ExecutionPlan,
    ) -> FinalTradeDecision:
        return FinalTradeDecision(
            status="NO_TRADE",
            symbol=execution_plan.symbol,
            side=execution_plan.side,
            recommendation=execution_plan.recommendation,
            approved_quantity=0.0,
            approved_value=0.0,
            approved_risk=0.0,
            conviction_score=conviction.score,
            execution_ready=False,
            risk_allowed=False,
            summary="Execution planner did not produce a tradable plan",
            reasons=execution_plan.reasons,
            warnings=execution_plan.warnings,
        )

    @classmethod
    def _no_trade_without_risk(
        cls,
        *,
        conviction: ConvictionResult,
        execution_plan: ExecutionPlan,
    ) -> FinalTradeDecision:
        return FinalTradeDecision(
            status="NO_TRADE",
            symbol=execution_plan.symbol,
            side=execution_plan.side,
            recommendation=execution_plan.recommendation,
            approved_quantity=0.0,
            approved_value=0.0,
            approved_risk=0.0,
            conviction_score=conviction.score,
            execution_ready=True,
            risk_allowed=False,
            summary="Execution plan requires account risk approval",
            reasons=(
                "Account risk context was not provided.",
            ),
            warnings=execution_plan.warnings,
        )

    @staticmethod
    def _merge_warnings(
        *warning_groups: tuple[str, ...],
    ) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                warning
                for group in warning_groups
                for warning in group
            )
        )
