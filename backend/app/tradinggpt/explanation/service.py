from __future__ import annotations

from app.tradinggpt.pipeline import TradingPipelineResult

from .models import TradingExplanation


class TradingExplanationEngine:
    """Build a deterministic human-readable trading explanation."""

    @classmethod
    def explain(
        cls,
        pipeline: TradingPipelineResult,
    ) -> TradingExplanation:
        conviction = pipeline.conviction
        scoring = pipeline.scoring
        market = pipeline.market_regime
        portfolio = pipeline.portfolio

        summary = (
            f"{conviction.recommendation} setup with "
            f"{conviction.level} conviction "
            f"({conviction.score:.1f}/100) in "
            f"{market.market_regime} market conditions."
        )

        thesis = cls._build_thesis(
            recommendation=conviction.recommendation,
            trade_direction=scoring.trade_direction,
            market_regime=market.market_regime,
        )

        pros = cls._build_pros(pipeline)
        cons = cls._build_cons(pipeline)
        risks = cls._build_risks(pipeline)

        return TradingExplanation(
            summary=summary,
            thesis=thesis,
            risk_level=portfolio.risk_level.upper(),
            pros=pros,
            cons=cons,
            risks=risks,
        )

    @staticmethod
    def _build_thesis(
        *,
        recommendation: str,
        trade_direction: str,
        market_regime: str,
    ) -> str:
        if recommendation in {"STRONG_BUY", "BUY"}:
            return (
                f"The analytical sources support a "
                f"{trade_direction.lower()} position. "
                f"The {market_regime} environment is compatible "
                f"with taking controlled market exposure."
            )

        if recommendation == "HOLD":
            return (
                "The available evidence is not strong enough "
                "to justify increasing or closing the position. "
                "Waiting for clearer confirmation is preferred."
            )

        if recommendation == "REDUCE":
            return (
                "The setup has weakened and current exposure "
                "should be reduced to limit portfolio risk."
            )

        return (
            "The risk-adjusted setup is unattractive. "
            "Opening new exposure should be avoided."
        )

    @staticmethod
    def _build_pros(
        pipeline: TradingPipelineResult,
    ) -> tuple[str, ...]:
        scoring = pipeline.scoring
        market = pipeline.market_regime
        conviction = pipeline.conviction

        pros: list[str] = []

        if scoring.signal_score >= 70:
            pros.append(
                f"Strong signal score: "
                f"{scoring.signal_score:.1f}/100."
            )

        if market.risk_appetite_score >= 65:
            pros.append(
                f"Supportive market risk appetite: "
                f"{market.risk_appetite_score:.1f}/100."
            )

        if scoring.consensus_score >= 65:
            pros.append(
                f"Good analytical consensus: "
                f"{scoring.consensus_score:.1f}/100."
            )

        if scoring.confidence >= 70:
            pros.append(
                f"High source confidence: "
                f"{scoring.confidence}/100."
            )

        if conviction.position_multiplier > 1:
            pros.append(
                "Conviction supports an increased position "
                f"multiplier of "
                f"{conviction.position_multiplier:.2f}."
            )

        if not pros:
            pros.append(
                "No individual positive factor reached "
                "the strong-support threshold."
            )

        return tuple(pros)

    @staticmethod
    def _build_cons(
        pipeline: TradingPipelineResult,
    ) -> tuple[str, ...]:
        scoring = pipeline.scoring
        market = pipeline.market_regime
        portfolio = pipeline.portfolio

        cons: list[str] = []

        if scoring.consensus_score < 60:
            cons.append(
                f"Analytical consensus is limited: "
                f"{scoring.consensus_score:.1f}/100."
            )

        if scoring.confidence < 60:
            cons.append(
                f"Source confidence is limited: "
                f"{scoring.confidence}/100."
            )

        if market.volatility_score >= 60:
            cons.append(
                f"Market volatility is elevated: "
                f"{market.volatility_score:.1f}/100."
            )

        if portfolio.portfolio_risk_score >= 60:
            cons.append(
                f"Portfolio risk is elevated: "
                f"{portfolio.portfolio_risk_score:.1f}/100."
            )

        if market.risk_environment == "RISK_OFF":
            cons.append(
                "The broader market environment is risk-off."
            )

        if not cons:
            cons.append(
                "No major negative factor crossed "
                "the configured warning threshold."
            )

        return tuple(cons)

    @staticmethod
    def _build_risks(
        pipeline: TradingPipelineResult,
    ) -> tuple[str, ...]:
        market = pipeline.market_regime
        portfolio = pipeline.portfolio

        risks: list[str] = [
            (
                "The recommendation is model-generated and "
                "must be validated against live prices, "
                "liquidity, fees, and execution conditions."
            )
        ]

        risks.extend(market.warnings)
        risks.extend(portfolio.warnings)

        if market.volatility_score >= 40:
            risks.append(
                "Market volatility may increase slippage "
                "and stop-loss execution risk."
            )

        if portfolio.invested_percent >= 80:
            risks.append(
                "The portfolio is already highly invested, "
                "which limits available risk capacity."
            )

        return tuple(dict.fromkeys(risks))
