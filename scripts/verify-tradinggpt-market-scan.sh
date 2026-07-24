#!/usr/bin/env bash

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"

echo "Checking TradingGPT market scanner..."

response="$(
  curl --fail --silent --show-error \
    -X POST "${API_URL}/api/v3/assistant/market-scan" \
    -H "Content-Type: application/json" \
    -d '{
      "assets": ["BTC", "ETH", "SOL"],
      "risk_level": "medium",
      "limit": 3
    }'
)"

echo "${response}" | python -m json.tool

echo "${response}" | python -c '
import json
import sys

payload = json.load(sys.stdin)

assert payload["scanned_assets"] == 3
assert payload["successful_assets"] >= 1
assert payload["failed_assets"] >= 0
assert isinstance(payload["ranking"], list)
assert len(payload["ranking"]) >= 1

for item in payload["ranking"]:
    assert item["asset"] in {"BTC", "ETH", "SOL"}
    assert item["symbol"].endswith("USDT")
    assert isinstance(item["score"], int | float)
    assert 15 <= item["confidence"] <= 100
    assert item["risk"] in {"low", "medium", "high"}
    assert item["recommendation"] in {
        "BUY",
        "CAUTIOUS_BUY",
        "WAIT",
        "CAUTIOUS_SELL",
        "AVOID_OR_REDUCE",
    }
    assert isinstance(item["quality_penalty"], int)
    assert isinstance(item["warnings"], list)

print("TradingGPT market scanner verification passed.")
'
