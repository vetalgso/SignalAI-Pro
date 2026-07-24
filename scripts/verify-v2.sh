#!/usr/bin/env sh
set -eu
API=${API_URL:-http://localhost:8000}
WEB=${WEB_URL:-http://localhost:3000}
check(){ echo "[CHECK] $1"; curl -fsS "$2" >/tmp/signalai-check.json; }
check health "$API/health"
check symbols "$API/api/v1/market/symbols?quote_asset=USDT"
check candles "$API/api/v1/market/klines?symbol=BTCUSDT&interval=1h&limit=20"
check signal "$API/api/v1/signal-engine/analyze?symbol=BTCUSDT&interval=1h&limit=250"
check forecast "$API/api/v2/forecasts/current?symbol=BTCUSDT&horizons=10,30,60"
check news "$API/api/v2/news?limit=3&asset=BTC"
check frontend "$WEB"
echo "ALL SIGNALAI PRO 2.0 BETA CHECKS PASSED"
