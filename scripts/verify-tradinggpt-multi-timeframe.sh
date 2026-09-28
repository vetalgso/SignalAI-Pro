#!/usr/bin/env bash

set -euo pipefail

docker compose exec -T api python - <<'PY'
from app.tradinggpt.scoring import ScoringEngine


def forecast(*items):
    return {"forecasts": list(items)}


def item(horizon, up, down):
    return {
        "horizon_minutes": horizon,
        "probabilities": {
            "up": up,
            "down": down,
            "flat": max(0.0, 1.0 - up - down),
        },
    }


aligned_long = forecast(
    item(15, 0.70, 0.15),
    item(60, 0.72, 0.13),
    item(240, 0.76, 0.10),
    item(1440, 0.80, 0.08),
)

aligned_short = forecast(
    item(15, 0.12, 0.72),
    item(60, 0.10, 0.75),
    item(240, 0.08, 0.80),
    item(1440, 0.06, 0.84),
)

counter_trend = forecast(
    item(15, 0.75, 0.10),
    item(60, 0.70, 0.15),
    item(240, 0.20, 0.65),
    item(1440, 0.10, 0.78),
)

mixed = forecast(
    item(15, 0.70, 0.15),
    item(60, 0.15, 0.70),
    item(240, 0.65, 0.20),
    item(1440, 0.20, 0.65),
)


long_result = ScoringEngine.timeframe_analysis(
    aligned_long,
    "LONG",
)

short_result = ScoringEngine.timeframe_analysis(
    aligned_short,
    "SHORT",
)

counter_result = ScoringEngine.timeframe_analysis(
    counter_trend,
    "LONG",
)

mixed_result = ScoringEngine.timeframe_analysis(
    mixed,
    "LONG",
)


assert long_result["trend_direction"] == "LONG"
assert long_result["trade_style"] == "TREND_FOLLOWING"
assert long_result["timeframe_consensus_score"] == 100.0

assert short_result["trend_direction"] == "SHORT"
assert short_result["trade_style"] == "TREND_FOLLOWING"
assert short_result["timeframe_consensus_score"] == 100.0

assert counter_result["trend_direction"] == "SHORT"
assert counter_result["trade_style"] == "COUNTER_TREND"
assert 50 < counter_result["timeframe_consensus_score"] < 100

assert mixed_result["timeframe_consensus_score"] < 100
assert set(mixed_result["directions"]) == {
    "15m",
    "1H",
    "4H",
    "1D",
}


ranking_aligned = ScoringEngine.ranking_score(
    opportunity_score=80,
    consensus_score=90,
    confidence=85,
    timeframe_consensus_score=100,
)

ranking_conflicted = ScoringEngine.ranking_score(
    opportunity_score=80,
    consensus_score=90,
    confidence=85,
    timeframe_consensus_score=55,
)

assert ranking_aligned > ranking_conflicted


# Ranking v2 compatibility must remain intact.
legacy_ranking = ScoringEngine.ranking_score(
    opportunity_score=85,
    consensus_score=95,
    confidence=90,
)

assert round(legacy_ranking, 2) == 88.25


print("TradingGPT Multi-Timeframe verification passed")
print("aligned LONG:", long_result)
print("aligned SHORT:", short_result)
print("counter trend:", counter_result)
print("mixed:", mixed_result)
print(
    "ranking:",
    {
        "aligned": round(ranking_aligned, 2),
        "conflicted": round(ranking_conflicted, 2),
        "legacy_v2": round(legacy_ranking, 2),
    },
)
PY
