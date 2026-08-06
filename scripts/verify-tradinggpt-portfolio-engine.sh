#!/usr/bin/env bash

set -euo pipefail

docker compose exec -T api python - <<'PY'
from app.tradinggpt.portfolio import PortfolioEngine


def assert_allocation(result) -> None:
    total = sum(
        position.target_percent
        for position in result.positions
    )

    assert abs(total - 100.0) < 0.000001, total


low = PortfolioEngine.build(
    risk_level="low",
    capital=10_000,
    max_position_percent=25,
)

medium = PortfolioEngine.build(
    risk_level="medium",
    capital=10_000,
    max_position_percent=25,
)

high_unrestricted = PortfolioEngine.build(
    risk_level="high",
    capital=10_000,
    max_position_percent=100,
)

high_limited = PortfolioEngine.build(
    risk_level="high",
    capital=10_000,
    max_position_percent=20,
)

rebalanced = PortfolioEngine.build(
    risk_level="medium",
    capital=20_000,
    max_position_percent=25,
    current_allocations={
        "BTC": 40,
        "ETH": 20,
        "NASDAQ ETF": 10,
        "DOGE": 5,
        "Cash / USD": 25,
    },
)


for result in (
    low,
    medium,
    high_unrestricted,
    high_limited,
    rebalanced,
):
    assert_allocation(result)
    assert 0 <= result.portfolio_risk_score <= 100
    assert result.invested_percent <= 100
    assert result.cash_reserve_percent >= 0


assert low.max_risk_per_trade_percent == 0.5
assert medium.max_risk_per_trade_percent == 1.0
assert high_limited.max_risk_per_trade_percent == 2.0

assert low.portfolio_risk_score < medium.portfolio_risk_score

# The 20% position cap moves excess BTC/ETH allocation into cash.
# Therefore the constrained high-risk portfolio may have a lower
# realized risk score than the unconstrained medium portfolio.
assert high_limited.portfolio_risk_score > low.portfolio_risk_score
assert high_limited.portfolio_risk_score < medium.portfolio_risk_score
assert (
    high_limited.portfolio_risk_score
    < high_unrestricted.portfolio_risk_score
)

high_positions = {
    position.asset: position
    for position in high_limited.positions
}

assert high_positions["BTC"].target_percent == 20
assert high_positions["ETH"].target_percent == 20
assert high_positions["Cash / USD"].target_percent == 25

for asset, position in high_positions.items():
    if asset != "Cash / USD":
        assert position.target_percent <= 20

assert high_limited.warnings


rebalanced_positions = {
    position.asset: position
    for position in rebalanced.positions
}

assert rebalanced_positions["BTC"].action == "REDUCE"
assert rebalanced_positions["ETH"].action == "HOLD"
assert rebalanced_positions["NASDAQ ETF"].action == "ADD"
assert rebalanced_positions["DOGE"].action == "AVOID"

assert rebalanced_positions["BTC"].amount == 5_000
assert rebalanced_positions["ETH"].amount == 4_000

serialized = rebalanced.to_dict()

assert serialized["capital"] == 20_000
assert serialized["currency"] == "USD"
assert serialized["portfolio_risk_score"] == (
    rebalanced.portfolio_risk_score
)
assert len(serialized["positions"]) == len(
    rebalanced.positions
)


try:
    PortfolioEngine.build(
        risk_level="medium",
        current_allocations={
            "BTC": 70,
            "ETH": 40,
        },
    )
except ValueError:
    pass
else:
    raise AssertionError(
        "Allocations above 100% must be rejected"
    )


print("TradingGPT Portfolio Engine verification passed")
print("low:", low.to_dict())
print("medium:", medium.to_dict())
print("high unrestricted:", high_unrestricted.to_dict())
print("high limited:", high_limited.to_dict())
print("rebalanced:", rebalanced.to_dict())
PY
