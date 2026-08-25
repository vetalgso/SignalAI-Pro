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

## Exchange execution safety

SignalAI Pro supports authenticated, encrypted, account-scoped Binance Spot Testnet execution:

- exchange preview and dry-run journal;
- explicitly confirmed TESTNET order submission;
- order history, status, open orders, and cancellation;
- server-side master switch, maximum order notional, and optional symbol allowlist;
- account-scoped UTC daily notional and open-order limits;
- serialized execution checks and live Testnet open-order counts prevent stale or parallel limit bypasses;
- dry runs do not consume limits, while reduce-only orders may reduce exposure;
- LIVE exchange execution remains blocked by the backend.

This project is not financial advice. TESTNET execution uses simulated exchange funds; do not enable LIVE trading without a separate production risk review.

### Automatic order reconciliation

The API can periodically refresh local `OPEN` and
`PARTIALLY_FILLED` Binance Testnet journal entries from
the remote order status.

The worker is read-only: it calls only the remote order
status operation and never submits or cancels orders.
A dedicated PostgreSQL advisory lock ensures that only
one API instance processes a batch at a time.

The worker is disabled by default. Enable it with
`ORDER_RECONCILIATION_BACKGROUND_ENABLED=true`.
The interval, batch size, history limit, and lock key
use the related `ORDER_RECONCILIATION_*` environment
variables. By default, the newest 100,000 completed
batch records are retained. Unfinished `STARTED`
records are preserved for failure investigation.
