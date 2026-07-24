# SignalAI Pro 2.0 RC1

Clean release candidate with FastAPI, PostgreSQL, Redis, React, TypeScript, Vite, Nginx, Binance public market data, current signals, 10/30/60-minute forecasts, news monitoring and backtesting.

## Install

```bash
cd /workspaces/SignalAI-Pro
unzip -o SignalAI-Pro-v2.0.0-rc1.zip -d /tmp/signalai-rc1
cp -a /tmp/signalai-rc1/. .
cp -n backend/.env.example backend/.env
./scripts/start.sh
```

## Verify

```bash
./scripts/verify-all.sh
```

Web UI: port `3000`  
Swagger: port `8000/docs`

## Clean rebuild

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

Do not add `-v` to `docker compose down` unless you intentionally want to delete PostgreSQL data.

This is an analytical prototype and does not place real orders.
