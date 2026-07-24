#!/usr/bin/env bash

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"

echo "Checking TradingGPT Assistant..."

response="$(
  curl --fail --silent --show-error \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{
      "message": "У меня 5000 долларов. Как распределить капитал?",
      "context": {
        "capital": 5000,
        "currency": "USD",
        "risk_level": "medium",
        "investment_horizon": "long",
        "preferred_markets": ["crypto", "stocks", "metals"]
      }
    }' \
    "${API_URL}/api/v3/assistant/chat"
)"

echo "${response}" | python -m json.tool

echo "${response}" | python -c '
import json
import sys

payload = json.load(sys.stdin)

assert payload["intent"] == "portfolio_allocation"
assert payload["confidence"] > 0
assert len(payload["portfolio"]) > 0

allocation = sum(item["allocation_percent"] for item in payload["portfolio"])
assert round(allocation, 2) == 100

print("TradingGPT Assistant verification passed.")
'
