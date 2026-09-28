from __future__ import annotations

from app.tradinggpt.conviction import (
    ConvictionEngine,
    ConvictionFactors,
)


def calculate(
    signal: float,
    market: float,
    portfolio: float,
    quality: float,
):
    return ConvictionEngine.calculate(
        factors=ConvictionFactors(
            signal_score=signal,
            market_score=market,
            portfolio_score=portfolio,
            quality_score=quality,
        )
    )


def verify_avoid() -> None:
    result = calculate(10, 20, 15, 10)

    assert result.score == 14.0
    assert result.level == "LOW"
    assert result.recommendation == "AVOID"
    assert result.position_multiplier == 0.25

    print("Avoid conviction verification passed")


def verify_reduce() -> None:
    result = calculate(40, 35, 30, 40)

    assert result.score == 36.5
    assert result.level == "LOW"
    assert result.recommendation == "REDUCE"
    assert result.position_multiplier == 0.5

    print("Reduce conviction verification passed")


def verify_hold() -> None:
    result = calculate(60, 55, 50, 65)

    assert result.score == 57.25
    assert result.level == "MEDIUM"
    assert result.recommendation == "HOLD"
    assert result.position_multiplier == 1.0

    print("Hold conviction verification passed")


def verify_buy() -> None:
    result = calculate(85, 75, 70, 80)

    assert result.score == 78.25
    assert result.level == "HIGH"
    assert result.recommendation == "BUY"
    assert result.position_multiplier == 1.25

    print("Buy conviction verification passed")


def verify_strong_buy() -> None:
    result = calculate(95, 90, 85, 95)

    assert result.score == 91.5
    assert result.level == "VERY_HIGH"
    assert result.recommendation == "STRONG_BUY"
    assert result.position_multiplier == 1.5

    print("Strong Buy conviction verification passed")


def verify_score_clamping() -> None:
    high = calculate(150, 150, 150, 150)
    low = calculate(-50, -50, -50, -50)

    assert high.score == 100.0
    assert high.confidence == 1.0
    assert low.score == 0.0
    assert low.confidence == 0.0

    print("Conviction score clamping verification passed")


def verify_serialization() -> None:
    result = calculate(80, 70, 60, 90)
    data = result.to_dict()

    assert data["score"] == 74.5
    assert data["level"] == "HIGH"
    assert data["recommendation"] == "BUY"
    assert data["factors"]["signal_score"] == 80
    assert len(data["reasons"]) == 4

    print("Conviction serialization verification passed")


def main() -> None:
    verify_avoid()
    verify_reduce()
    verify_hold()
    verify_buy()
    verify_strong_buy()
    verify_score_clamping()
    verify_serialization()

    print("TradingGPT Conviction Engine verification passed")


if __name__ == "__main__":
    main()
