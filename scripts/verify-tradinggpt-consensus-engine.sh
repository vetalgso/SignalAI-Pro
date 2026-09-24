#!/usr/bin/env bash

set -euo pipefail

docker compose exec -T api python - <<'PY'
from app.tradinggpt.scoring.engine import ScoringEngine


aligned_long = ScoringEngine.consensus_score(
    combined_direction="LONG",
    signal_score=90,
    forecast_score=80,
    news_score=75,
    signal_available=True,
    forecast_available=True,
    news_available=True,
)

aligned_short = ScoringEngine.consensus_score(
    combined_direction="SHORT",
    signal_score=10,
    forecast_score=20,
    news_score=25,
    signal_available=True,
    forecast_available=True,
    news_available=True,
)

conflicted_long = ScoringEngine.consensus_score(
    combined_direction="LONG",
    signal_score=90,
    forecast_score=20,
    news_score=15,
    signal_available=True,
    forecast_available=True,
    news_available=True,
)

neutral = ScoringEngine.consensus_score(
    combined_direction="NEUTRAL",
    signal_score=90,
    forecast_score=10,
    news_score=50,
    signal_available=True,
    forecast_available=True,
    news_available=True,
)

assert aligned_long == 100.0
assert aligned_short == 100.0
assert conflicted_long < 50.0
assert neutral == 50.0


aligned_opportunity = ScoringEngine.opportunity_score(
    score=85,
    confidence=70,
    consensus_score=100,
)

neutral_consensus_opportunity = ScoringEngine.opportunity_score(
    score=85,
    confidence=70,
    consensus_score=50,
)

conflicted_opportunity = ScoringEngine.opportunity_score(
    score=85,
    confidence=70,
    consensus_score=0,
)

assert aligned_opportunity > neutral_consensus_opportunity
assert neutral_consensus_opportunity > conflicted_opportunity


long_result = ScoringEngine.evaluate(
    signal={
        "decision": {
            "action": "LONG",
            "confidence": 80,
        }
    },
    forecast={
        "forecasts": [
            {
                "horizon_minutes": 60,
                "probabilities": {
                    "up": 0.85,
                    "down": 0.05,
                },
            },
            {
                "horizon_minutes": 240,
                "probabilities": {
                    "up": 0.80,
                    "down": 0.10,
                },
            },
        ]
    },
    news={
        "articles": [
            {
                "sentiment": "positive",
                "impact_score": 80,
            },
        ]
    },
)

short_result = ScoringEngine.evaluate(
    signal={
        "decision": {
            "action": "SHORT",
            "confidence": 80,
        }
    },
    forecast={
        "forecasts": [
            {
                "horizon_minutes": 60,
                "probabilities": {
                    "up": 0.05,
                    "down": 0.85,
                },
            },
            {
                "horizon_minutes": 240,
                "probabilities": {
                    "up": 0.10,
                    "down": 0.80,
                },
            },
        ]
    },
    news={
        "articles": [
            {
                "sentiment": "negative",
                "impact_score": 80,
            },
        ]
    },
)

assert long_result.trade_direction == "LONG"
assert short_result.trade_direction == "SHORT"

assert long_result.consensus_score == 100.0
assert short_result.consensus_score == 100.0

assert long_result.opportunity_score > 0
assert short_result.opportunity_score > 0


print("TradingGPT Consensus Engine verification passed")
print(
    "aligned_long:",
    round(aligned_long, 2),
)
print(
    "aligned_short:",
    round(aligned_short, 2),
)
print(
    "conflicted_long:",
    round(conflicted_long, 2),
)
print(
    "opportunity comparison:",
    {
        "aligned": round(aligned_opportunity, 2),
        "neutral": round(neutral_consensus_opportunity, 2),
        "conflicted": round(conflicted_opportunity, 2),
    },
)
print(
    "LONG result:",
    {
        "score": round(long_result.score, 2),
        "opportunity": round(long_result.opportunity_score, 2),
        "consensus": round(long_result.consensus_score, 2),
        "confidence": long_result.confidence,
        "direction": long_result.trade_direction,
    },
)
print(
    "SHORT result:",
    {
        "score": round(short_result.score, 2),
        "opportunity": round(short_result.opportunity_score, 2),
        "consensus": round(short_result.consensus_score, 2),
        "confidence": short_result.confidence,
        "direction": short_result.trade_direction,
    },
)
PY
