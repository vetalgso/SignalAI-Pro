# SignalAI Pro v0.5.0 verification

No database migration is required for this release.

## Build and start

```bash
docker compose down
docker compose build --no-cache api
docker compose up -d
```

## Verify API

```bash
docker compose ps
docker compose logs api --tail=100
curl http://localhost:8000/health
```

## Calculate BTC indicators

```bash
curl -s 'http://localhost:8000/api/v1/indicators?symbol=BTCUSDT&interval=1h&limit=250' | python -m json.tool
```

## Other examples

```bash
curl -s 'http://localhost:8000/api/v1/indicators?symbol=ETHUSDT&interval=15m&limit=250' | python -m json.tool
curl -s 'http://localhost:8000/api/v1/indicators?symbol=SOLUSDT&interval=4h&limit=300' | python -m json.tool
```

The response includes EMA 20/50/200, SMA 20/50, RSI 14, MACD, Bollinger Bands, ATR 14, ADX 14, volume context and a compact market-state summary.
