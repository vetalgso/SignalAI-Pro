#!/usr/bin/env sh
set -eu
API=${API_URL:-http://localhost:8000}
UI=${UI_URL:-http://localhost:3000}
check(){ name=$1; url=$2; echo "[CHECK] $name"; curl -fsS "$url" >/tmp/signalai-check.json; echo "[OK] $name"; }
check "Health" "$API/health"
check "Binance status" "$API/api/v1/market/status"
check "Ticker" "$API/api/v1/market/ticker?symbol=BTCUSDT"
check "Klines" "$API/api/v1/market/klines?symbol=BTCUSDT&interval=1h&limit=5"
check "Indicators" "$API/api/v1/indicators?symbol=BTCUSDT&interval=1h&limit=250"
check "Signal Engine" "$API/api/v1/signal-engine/analyze?symbol=BTCUSDT&interval=1h&limit=250"
check "Backtest" "$API/api/v1/backtest?symbol=BTCUSDT&interval=1h&limit=300"
check "Web interface" "$UI"
echo "ALL SIGNALAI PRO CHECKS PASSED"
