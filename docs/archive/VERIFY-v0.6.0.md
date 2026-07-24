# SignalAI Pro v0.6.0 verification

## Preview a signal

```bash
curl -s 'http://localhost:8000/api/v1/signal-engine/analyze?symbol=BTCUSDT&interval=1h&limit=250' | python -m json.tool
```

The response action is `LONG`, `SHORT`, or `WAIT`. An actionable result includes Entry, Stop Loss, Take Profit, a 2:1 risk/reward ratio, confidence, score details, reasons, warnings, and the complete indicator snapshot.

## Generate and save

Authenticate in Swagger and call `POST /api/v1/signal-engine/generate`. The endpoint saves only actionable LONG/SHORT signals. A WAIT result returns HTTP 409 and is not stored.

## Verify saved signals

```bash
curl -s 'http://localhost:8000/api/v1/signals?limit=10' | python -m json.tool
```
