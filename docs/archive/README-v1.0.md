# SignalAI Pro v1.0 MVP

Complete runnable MVP: FastAPI, PostgreSQL, Redis, JWT auth, Binance public market data, technical indicators, signal engine, historical backtest and web dashboard.

## Start

```bash
cp backend/.env.example backend/.env  # only if .env does not exist
# Set JWT_SECRET_KEY in backend/.env
docker compose up -d --build
./scripts/verify-all.sh
```

Dashboard: http://localhost:3000  
Swagger: http://localhost:8000/docs

Backtest is an engineering evaluation, not proof of future profitability. It excludes fees, slippage and funding.
