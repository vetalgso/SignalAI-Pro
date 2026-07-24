# SignalAI Pro v0.6.0

SignalAI Pro is a FastAPI-based trading signal platform with PostgreSQL, Redis, JWT authentication, Binance public market data, technical indicators, and a deterministic technical-confluence Signal Engine.

## v0.6.0 additions

- `GET /api/v1/signal-engine/analyze`
- `POST /api/v1/signal-engine/generate` (JWT required)
- LONG / SHORT / WAIT decisions
- 0-100 directional scoring and confidence
- ATR-based Entry, Stop Loss, and Take Profit
- Fixed 2:1 initial risk/reward ratio
- Human-readable reasons and risk warnings
- Actionable signals can be saved to PostgreSQL

This release is an analytical prototype, not financial advice. It does not place orders.
