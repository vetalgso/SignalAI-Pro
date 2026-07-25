#!/usr/bin/env bash

set -euo pipefail

docker compose exec -T api python - <<'PY'
from app.tradinggpt.modules.crypto_asset import (
    CryptoAssetAnalysisModule,
)
from app.tradinggpt.schemas import (
    AssistantChatRequest,
    InvestorContext,
)


module = CryptoAssetAnalysisModule()

request = AssistantChatRequest(
    message="Стоит ли покупать BTC?",
    context=InvestorContext(
        risk_level="medium",
        investment_horizon="medium",
    ),
)

signal = {
    "decision": {
        "action": "LONG",
        "confidence": 82,
        "score": {
            "long_score": 82,
            "short_score": 18,
        },
        "reasons": [
            "Momentum and trend indicators support growth."
        ],
        "warnings": [],
    },
    "indicators": {
        "volume": {
            "ratio": 1.2,
        }
    },
}

forecast = {
    "forecasts": [
        {
            "horizon_minutes": 15,
            "direction": "UP",
            "confidence": 72,
            "expected_change_percent": 0.4,
            "probabilities": {
                "up": 0.72,
                "down": 0.13,
                "flat": 0.15,
            },
            "risk_level": "normal",
        },
        {
            "horizon_minutes": 60,
            "direction": "UP",
            "confidence": 76,
            "expected_change_percent": 0.8,
            "probabilities": {
                "up": 0.76,
                "down": 0.10,
                "flat": 0.14,
            },
            "risk_level": "normal",
        },
        {
            "horizon_minutes": 240,
            "direction": "UP",
            "confidence": 79,
            "expected_change_percent": 1.5,
            "probabilities": {
                "up": 0.79,
                "down": 0.08,
                "flat": 0.13,
            },
            "risk_level": "normal",
        },
        {
            "horizon_minutes": 1440,
            "direction": "UP",
            "confidence": 83,
            "expected_change_percent": 3.0,
            "probabilities": {
                "up": 0.83,
                "down": 0.07,
                "flat": 0.10,
            },
            "risk_level": "normal",
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
            "sentiment": "positive",
            "impact_score": 65,
        },
        {
            "sentiment": "neutral",
            "impact_score": 40,
        },
    ]
}

response = module._build_response(
    asset="BTC",
    symbol="BTCUSDT",
    request=request,
    signal=signal,
    forecast=forecast,
    news=news,
    available_sources=3,
)

details = response.details

required_fields = {
    "trade_direction",
    "opportunity_score",
    "consensus_score",
    "timeframe_consensus_score",
    "ranking_score",
    "timeframe_directions",
    "timeframe_scores",
    "trend_direction",
    "trade_style",
    "reasons",
}

missing = required_fields - details.keys()

assert not missing, f"Missing details fields: {missing}"

assert details["trade_direction"] == "LONG"
assert details["trend_direction"] == "LONG"
assert details["trade_style"] == "TREND_FOLLOWING"
assert details["timeframe_consensus_score"] == 100.0

assert details["timeframe_directions"] == {
    "15m": "LONG",
    "1H": "LONG",
    "4H": "LONG",
    "1D": "LONG",
}

assert 0 <= details["opportunity_score"] <= 100
assert 0 <= details["consensus_score"] <= 100
assert 0 <= details["ranking_score"] <= 100
assert details["reasons"]

factor_types = {
    factor.type
    for factor in response.factors
}

assert "timeframe_alignment" in factor_types

assert "Направление сделки: LONG." in response.answer
assert "Основной тренд: LONG." in response.answer
assert "Тип сделки: TREND_FOLLOWING." in response.answer
assert (
    "Согласованность аналитических источников"
    in response.answer
)

print("TradingGPT Asset Explainability verification passed")
print(
    {
        "recommendation": details["recommendation"],
        "trade_direction": details["trade_direction"],
        "opportunity_score": details["opportunity_score"],
        "consensus_score": details["consensus_score"],
        "timeframe_consensus_score": (
            details["timeframe_consensus_score"]
        ),
        "ranking_score": details["ranking_score"],
        "trend_direction": details["trend_direction"],
        "trade_style": details["trade_style"],
    }
)
print(response.answer)
PY
