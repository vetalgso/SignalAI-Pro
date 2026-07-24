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

forecast = {
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

news = {
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


assert ScoringEngine.signal_score(None) == 50.0
assert ScoringEngine.signal_score(long_signal) == 90.0
assert ScoringEngine.signal_score(short_signal) == 10.0
assert ScoringEngine.signal_score(neutral_signal) == 50.0

forecast_score = ScoringEngine.forecast_score(forecast)
news_score = ScoringEngine.news_score(news)

assert 50 < forecast_score <= 100
assert 50 < news_score <= 100

result = ScoringEngine.evaluate(
    signal=long_signal,
    forecast=forecast,
    news=news,
)

assert result.score > 50
assert result.confidence >= 20
assert result.signal_score == 90.0
assert result.forecast_score == forecast_score
assert result.news_score == news_score

assert ScoringEngine.recommendation(70, 50) == "BUY"
assert ScoringEngine.recommendation(60, 50) == "CAUTIOUS_BUY"
assert ScoringEngine.recommendation(30, 50) == "AVOID_OR_REDUCE"
assert ScoringEngine.recommendation(40, 50) == "CAUTIOUS_SELL"
assert ScoringEngine.recommendation(70, 30) == "WAIT"

print("TradingGPT ScoringEngine verification passed")
print("score:", round(result.score, 2))
print("confidence:", result.confidence)
print("signal_score:", result.signal_score)
print("forecast_score:", round(result.forecast_score, 2))
print("news_score:", round(result.news_score, 2))
PY
