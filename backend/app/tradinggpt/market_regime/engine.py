from __future__ import annotations

from collections.abc import Iterable

from app.tradinggpt.market_regime.indicators import (
    build_asset_signals,
    clamp,
    market_breadth_score,
    weighted_directional_score,
    weighted_volatility_score,
)
from app.tradinggpt.market_regime.models import (
    AssetRegimeSignal,
    MarketObservation,
    MarketRegime,
    MarketRegimeResult,
    MarketTrend,
    RiskEnvironment,
)


def _signals_by_role(
    signals: Iterable[AssetRegimeSignal],
    role: str,
) -> tuple[AssetRegimeSignal, ...]:
    return tuple(
        signal
        for signal in signals
        if signal.role == role
    )


def _classify_trend(score: float) -> MarketTrend:
    if score >= 20:
        return "BULL"

    if score <= -20:
        return "BEAR"

    return "SIDEWAYS"


def _classify_risk_environment(
    risk_appetite_score: float,
) -> RiskEnvironment:
    if risk_appetite_score >= 15:
        return "RISK_ON"

    if risk_appetite_score <= -15:
        return "RISK_OFF"

    return "NEUTRAL"


def _classify_market_regime(
    trend_regime: MarketTrend,
    risk_environment: RiskEnvironment,
    volatility_score: float,
) -> MarketRegime:
    if volatility_score >= 75:
        return "HIGH_VOLATILITY"

    if risk_environment == "RISK_ON":
        return "RISK_ON"

    if risk_environment == "RISK_OFF":
        return "RISK_OFF"

    if trend_regime == "BULL":
        return "BULL"

    if trend_regime == "BEAR":
        return "BEAR"

    return "SIDEWAYS"


def _confidence(
    risk_appetite_score: float,
    breadth_score: float,
    volatility_score: float,
    signal_count: int,
) -> float:
    direction_strength = min(
        abs(risk_appetite_score) / 100.0,
        1.0,
    )
    breadth_strength = min(
        abs(breadth_score),
        1.0,
    )
    data_strength = min(
        signal_count / 6.0,
        1.0,
    )
    volatility_penalty = (
        max(volatility_score - 80.0, 0.0)
        / 100.0
    )

    score = (
        direction_strength * 0.45
        + breadth_strength * 0.30
        + data_strength * 0.25
        - volatility_penalty * 0.15
    )

    return clamp(score, 0.0, 1.0)


def _build_reasons(
    market_regime: MarketRegime,
    trend_regime: MarketTrend,
    risk_environment: RiskEnvironment,
    risk_asset_score: float,
    defensive_asset_score: float,
    breadth_score: float,
    volatility_score: float,
) -> tuple[str, ...]:
    reasons = [
        f"Market regime classified as {market_regime}.",
        f"Trend regime is {trend_regime}.",
        f"Risk environment is {risk_environment}.",
        (
            "Risk assets directional score: "
            f"{risk_asset_score:.2f}."
        ),
        (
            "Defensive assets directional score: "
            f"{defensive_asset_score:.2f}."
        ),
        f"Market breadth score: {breadth_score:.2f}.",
        f"Volatility score: {volatility_score:.2f}.",
    ]

    return tuple(reasons)


def _build_warnings(
    signals: tuple[AssetRegimeSignal, ...],
    volatility_score: float,
) -> tuple[str, ...]:
    warnings: list[str] = []

    if len(signals) < 3:
        warnings.append(
            "Low market coverage: fewer than three assets."
        )

    if not any(
        signal.role == "risk"
        for signal in signals
    ):
        warnings.append(
            "No risk assets were provided."
        )

    if not any(
        signal.role == "defensive"
        for signal in signals
    ):
        warnings.append(
            "No defensive assets were provided."
        )

    if volatility_score >= 75:
        warnings.append(
            "High volatility may reduce regime stability."
        )

    return tuple(warnings)


class MarketRegimeEngine:
    def analyze(
        self,
        observations: Iterable[MarketObservation],
    ) -> MarketRegimeResult:
        observation_list = tuple(observations)

        if not observation_list:
            raise ValueError(
                "at least one market observation is required"
            )

        signals = build_asset_signals(
            observation_list
        )

        risk_signals = _signals_by_role(
            signals,
            "risk",
        )
        defensive_signals = _signals_by_role(
            signals,
            "defensive",
        )

        risk_asset_score = weighted_directional_score(
            risk_signals
        )
        defensive_asset_score = (
            weighted_directional_score(
                defensive_signals
            )
        )

        risk_appetite_score = clamp(
            risk_asset_score
            - defensive_asset_score * 0.60,
            -100.0,
            100.0,
        )

        all_asset_score = weighted_directional_score(
            signals
        )
        trend_regime = _classify_trend(
            all_asset_score
        )

        risk_environment = (
            _classify_risk_environment(
                risk_appetite_score
            )
        )

        volatility_score = (
            weighted_volatility_score(
                signals
            )
        )
        breadth_score = market_breadth_score(
            signals
        )

        market_regime = _classify_market_regime(
            trend_regime=trend_regime,
            risk_environment=risk_environment,
            volatility_score=volatility_score,
        )

        confidence = _confidence(
            risk_appetite_score=risk_appetite_score,
            breadth_score=breadth_score,
            volatility_score=volatility_score,
            signal_count=len(signals),
        )

        return MarketRegimeResult(
            market_regime=market_regime,
            confidence=confidence,
            trend_regime=trend_regime,
            risk_environment=risk_environment,
            risk_asset_score=risk_asset_score,
            defensive_asset_score=(
                defensive_asset_score
            ),
            risk_appetite_score=risk_appetite_score,
            market_breadth_score=breadth_score,
            volatility_score=volatility_score,
            signals=signals,
            reasons=_build_reasons(
                market_regime=market_regime,
                trend_regime=trend_regime,
                risk_environment=risk_environment,
                risk_asset_score=risk_asset_score,
                defensive_asset_score=(
                    defensive_asset_score
                ),
                breadth_score=breadth_score,
                volatility_score=volatility_score,
            ),
            warnings=_build_warnings(
                signals=signals,
                volatility_score=volatility_score,
            ),
        )
