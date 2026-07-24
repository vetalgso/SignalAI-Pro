# SignalAI Pro v1.1.0 — Markets, Languages and Charts

## New
- Dynamic list of current Binance Spot trading pairs from `/api/v3/exchangeInfo`.
- Searchable trading-pair selector and quote-asset filter.
- Russian / English interface switch persisted in browser storage.
- Interactive candlestick chart that follows the selected pair and timeframe.
- New API endpoint: `GET /api/v1/market/symbols`.

## Run
```bash
docker compose down
docker compose up -d --build
./scripts/verify-all.sh
```

Open frontend on port 3000 and Swagger on port 8000.
