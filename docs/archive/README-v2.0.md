# SignalAI Pro 2.0 Beta 1

Integrated beta with React + TypeScript terminal, Binance pair selector, candlestick chart, current technical signal, transparent 10/30/60 minute probabilistic forecasts, and crypto RSS news intelligence.

## Run

```bash
cp backend/.env.example backend/.env  # only when .env does not exist
docker compose down
docker compose up -d --build
./scripts/verify-v2.sh
```

Frontend: port 3000. API docs: port 8000/docs.

## Important

Future Signal is currently a transparent heuristic baseline, not a trained ML model. News sentiment is keyword-based and articles are marked unverified until confirmation logic is added. No real orders are placed.
