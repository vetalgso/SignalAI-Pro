# SignalAI Pro v0.4.0 verification

No new database migration is required.

```bash
docker compose down
docker compose build --no-cache api
docker compose up -d

docker compose logs api --tail=100
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/market/status
curl 'http://localhost:8000/api/v1/market/ticker?symbol=BTCUSDT'
curl 'http://localhost:8000/api/v1/market/klines?symbol=BTCUSDT&interval=1h&limit=5'
```

Expected: HTTP 200 responses with live Binance Spot market data.
