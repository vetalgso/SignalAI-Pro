#!/usr/bin/env bash

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"

echo "Checking live TradingGPT asset analysis..."

response="$(
  curl --fail --silent --show-error \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{
      "message": "Стоит ли покупать BTC?",
      "context": {
        "capital": 5000,
        "currency": "USD",
        "risk_level": "medium",
        "investment_horizon": "long",
        "max_position_percent": 25
      }
    }' \
    "${API_URL}/api/v3/assistant/chat"
)"

echo "${response}" | python -m json.tool

echo "${response}" | python -c '
import json
import sys

payload = json.load(sys.stdin)

assert payload["intent"] == "asset_analysis"
assert payload["details"]["asset"] == "BTC"
assert payload["details"]["symbol"] == "BTCUSDT"
assert payload["details"]["sources_available"] >= 1
assert payload["details"]["recommendation"] in {
    "BUY",
    "CAUTIOUS_BUY",
    "WAIT",
    "CAUTIOUS_SELL",
    "AVOID_OR_REDUCE",
}
assert len(payload["factors"]) == 4
assert "quality_penalty" in payload["details"]
assert "quality_warnings" in payload["details"]
assert payload["risk"] in {"medium", "high"}
assert any(
    factor["type"] == "data_quality"
    for factor in payload["factors"]
)

print("Live TradingGPT asset analysis verification passed.")
'
