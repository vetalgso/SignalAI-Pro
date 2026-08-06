#!/usr/bin/env bash

set -euo pipefail

docker compose exec -T api python - <<'PY'
from app.tradinggpt.scoring import ScoringEngine


long_signal = {
    "decision": {
        "action": "LONG",
        "confidence": 80,
        "score": {},
    }
}

short_signal = {
    "decision": {
        "action": "SHORT",
        "confidence": 80,
        "score": {},
    }
}

neutral_signal = {
    "decision": {
        "action": "WAIT",
        "confidence": 20,
        "score": {
            "long_score": 40,
            "short_score": 40,
        },
    }
}

bullish_forecast = {
    "forecasts": [
        {
            "horizon_minutes": 60,
            "probabilities": {
                "up": 0.70,
                "down": 0.20,
                "sideways": 0.10,
            },
        },
        {
            "horizon_minutes": 1440,
            "probabilities": {
                "up": 0.60,
                "down": 0.25,
                "sideways": 0.15,
            },
        },
    ]
}

bearish_forecast = {
    "forecasts": [
        {
            "horizon_minutes": 60,
            "probabilities": {
                "up": 0.15,
                "down": 0.75,
                "sideways": 0.10,
            },
        },
        {
            "horizon_minutes": 1440,
            "probabilities": {
                "up": 0.20,
                "down": 0.65,
                "sideways": 0.15,
            },
        },
    ]
}

positive_news = {
    "articles": [
        {
            "sentiment": "positive",
            "impact_score": 80,
        },
        {
            "sentiment": "neutral",
            "impact_score": 40,
        },
    ]
}

negative_news = {
    "articles": [
        {
            "sentiment": "negative",
            "impact_score": 80,
        },
        {
            "sentiment": "neutral",
            "impact_score": 40,
        },
    ]
}


assert ScoringEngine.signal_score(None) == 50.0
assert ScoringEngine.signal_score(long_signal) == 90.0
assert ScoringEngine.signal_score(short_signal) == 10.0
assert ScoringEngine.signal_score(neutral_signal) == 50.0

long_result = ScoringEngine.evaluate(
    signal=long_signal,
    forecast=bullish_forecast,
    news=positive_news,
)

short_result = ScoringEngine.evaluate(
    signal=short_signal,
    forecast=bearish_forecast,
    news=negative_news,
)

assert long_result.score > 50
assert long_result.trade_direction == "LONG"
assert long_result.opportunity_score > 0

assert short_result.score < 50
assert short_result.trade_direction == "SHORT"
assert short_result.opportunity_score > 0

assert ScoringEngine.trade_direction(70) == "LONG"
assert ScoringEngine.trade_direction(30) == "SHORT"
assert ScoringEngine.trade_direction(50) == "NEUTRAL"

print(
    "recommendation samples:",
    {
        "90/90": ScoringEngine.recommendation(90, 90),
        "10/90": ScoringEngine.recommendation(10, 90),
        "85/60": ScoringEngine.recommendation(85, 60),
        "15/60": ScoringEngine.recommendation(15, 60),
        "70/60": ScoringEngine.recommendation(70, 60),
    },
)

assert ScoringEngine.recommendation(
    90,
    90,
    ScoringEngine.opportunity_score(90, 90, 100),
) == "LONG"

assert ScoringEngine.recommendation(
    10,
    90,
    ScoringEngine.opportunity_score(10, 90, 100),
) == "SHORT"

assert ScoringEngine.recommendation(70, 60) == "WAIT"
assert ScoringEngine.recommendation(30, 60) == "WAIT"

assert ScoringEngine.recommendation(
    85,
    60,
    ScoringEngine.opportunity_score(85, 60, 100),
) == "CAUTIOUS_BUY"

assert ScoringEngine.recommendation(
    15,
    60,
    ScoringEngine.opportunity_score(15, 60, 100),
) == "CAUTIOUS_SHORT"
assert ScoringEngine.recommendation(90, 30) == "WAIT"
assert ScoringEngine.recommendation(50, 90) == "WAIT"

print("TradingGPT Opportunity Engine verification passed")
print(
    "LONG:",
    round(long_result.score, 2),
    round(long_result.opportunity_score, 2),
    long_result.confidence,
    long_result.trade_direction,
)
print(
    "SHORT:",
    round(short_result.score, 2),
    round(short_result.opportunity_score, 2),
    short_result.confidence,
    short_result.trade_direction,
)
PY
