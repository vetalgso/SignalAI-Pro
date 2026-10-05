from __future__ import annotations

from collections.abc import Iterable

from app.tradinggpt.market_regime.models import (
    AssetRegimeSignal,
    AssetSignal,
    MarketObservation,
)
from app.tradinggpt.market_regime.presets import (
    asset_role,
    asset_weight,
    normalize_asset,
)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def directional_score(observation: MarketObservation) -> float:
    score = (
        observation.trend_score * 0.60
        + observation.momentum_score * 0.40
    )
    return clamp(score, -100.0, 100.0)


def classify_signal(
    score: float,
    threshold: float = 15.0,
) -> AssetSignal:
    if score >= threshold:
        return "UP"
    if score <= -threshold:
        return "DOWN"
    return "FLAT"


def build_asset_signal(
    observation: MarketObservation,
) -> AssetRegimeSignal:
    asset = normalize_asset(observation.asset)
    score = directional_score(observation)

    weight = (
        observation.weight
        if observation.weight is not None
        else asset_weight(asset)
    )

    return AssetRegimeSignal(
        asset=asset,
        role=asset_role(asset),
        signal=classify_signal(score),
        directional_score=score,
        volatility_score=observation.volatility_score,
        weight=weight,
    )


def build_asset_signals(
    observations: Iterable[MarketObservation],
) -> tuple[AssetRegimeSignal, ...]:
    return tuple(
        build_asset_signal(observation)
        for observation in observations
    )


def weighted_directional_score(
    signals: Iterable[AssetRegimeSignal],
) -> float:
    signal_list = tuple(signals)

    if not signal_list:
        return 0.0

    total_weight = sum(
        signal.weight
        for signal in signal_list
    )

    if total_weight <= 0:
        return 0.0

    weighted_sum = sum(
        signal.directional_score * signal.weight
        for signal in signal_list
    )

    return clamp(
        weighted_sum / total_weight,
        -100.0,
        100.0,
    )


def weighted_volatility_score(
    signals: Iterable[AssetRegimeSignal],
) -> float:
    signal_list = tuple(signals)

    if not signal_list:
        return 0.0

    total_weight = sum(
        signal.weight
        for signal in signal_list
    )

    if total_weight <= 0:
        return 0.0

    weighted_sum = sum(
        signal.volatility_score * signal.weight
        for signal in signal_list
    )

    return clamp(
        weighted_sum / total_weight,
        0.0,
        100.0,
    )


def market_breadth_score(
    signals: Iterable[AssetRegimeSignal],
) -> float:
    signal_list = tuple(signals)

    if not signal_list:
        return 0.0

    bullish = sum(
        1
        for signal in signal_list
        if signal.signal == "UP"
    )

    bearish = sum(
        1
        for signal in signal_list
        if signal.signal == "DOWN"
    )

    return clamp(
        (bullish - bearish) / len(signal_list),
        -1.0,
        1.0,
    )
