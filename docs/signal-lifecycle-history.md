# Signal lifecycle history recovery

The lifecycle tracker previously requested the latest 250 one-minute candles.
After a longer outage it could miss earlier stops/targets, then overwrite
`updated_at` with the time of the price check. A later retry could no longer
recover the missing window. This change separates verified candle progress
from record modification time.

## Processing contract

- Supported history feed: Binance **Spot**, `1m`. Other exchanges/market types
  are explicitly `UNSUPPORTED`; they must not consume Spot candles by accident.
- New signals start at the **first full minute at or after generated_at**.
  The partial creation minute is excluded because OHLC cannot separate prices
  before signal creation from prices after it. A price snapshot is not a tick
  history and is no longer used as a synthetic candle to bypass this boundary.
- Only closed minutes are processed. Entry recognition can therefore be later
  than before (up to approximately two minutes plus polling latency at creation).
  `CURRENT` means the supported full-minute window is caught up, **not** that
  the first partial minute, tick order, fills, or realized P&L are verified.
- `lifecycle_next_candle_at` is an exclusive cursor: the next minute to fetch.
  The request explicitly supplies UTC `startTime` and inclusive `endTime` for
  `[cursor, end)`. Pages contain at most 1000 minutes, one page per signal per
  cycle. Several cycles recover a longer outage from oldest to newest.
- Pages are uncached and independent of indicator/snapshot calculation. Each
  request has the market-data timeout. Existing per-cycle signal limit remains
  500; recovery can increase request volume and cycle duration on large cohorts.
- Missing, short, duplicate, unordered, shifted, malformed or unclosed candles
  reject the page. No current-price fallback, expiration or cursor advance is
  allowed across that gap. The complete page is validated before transitions;
  a bad row anywhere in it conservatively defers the whole page.
- Signal row locks and cursor/status rechecks prevent a stale fetched page from
  overwriting another worker or a manual transition. All page transitions,
  corresponding Telegram outbox records, price and cursor commit together.
  Failed transactions retry from the old cursor without duplicate deliveries.
- The existing within-candle stop-first policy remains. Candle OHLC does not
  establish tick order or execution price. If a candle touching entry straddles
  an intra-minute expiry deadline, processing stops as ambiguous instead of
  inventing which side of the deadline the entry occurred on.
- An ACTIVE signal expires only after its entry window has been covered. Wall
  time alone cannot expire a signal while an earlier page remains unprocessed.
- Market candle times remain in event payloads (`candle.opened_at`,
  `history.covered_until`); event `created_at`, `entry_reached_at` and `closed_at`
  retain their existing meaning as recording times. No historical timestamps
  are silently rewritten. Backfilled transitions use the existing outbox and
  can generate delayed notifications when notification dispatch is enabled.

Binance protocol reference:
[Spot Kline/Candlestick data](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market#klinecandlestick-data).

## Migration and existing signals

Migration `20260917_0022` adds nullable `lifecycle_next_candle_at` and
`lifecycle_history_status` (server default `UNVERIFIED`). Existing signals,
events and outbox records are preserved; the migration does not infer cursors
from `updated_at` or replay past transitions.

**Existing open signals with unverified history are held** and reported as
`HISTORY_UNVERIFIED`. They need a separately reviewed reconciliation; this
patch does not provide a reset/replay operation for them. Existing terminal
signals are never reopened. The 16 terminal signals in the supplied audit
remain historical records, not newly verified outcomes.

New signals created through the signal service receive a cursor and `PENDING`.
Signals inserted directly into the database remain `UNVERIFIED`. A manual
status override clears the cursor and marks the history `UNVERIFIED`; automatic
tracking of that signal pauses pending explicit reconciliation. This is a
material behavior change, not a transparent continuation after manual edits.

## Visibility

Signal list/detail responses include both new fields. The quality report's
origin filter retains its current semantics: **AUTOMATIC is not proof of full
history coverage**. This patch does not relabel or exclude legacy report rows.
There is no new frontend coverage badge in this backend change.

| Status | Meaning |
| --- | --- |
| `PENDING` | No full minute processed yet |
| `CURRENT` | Contiguous full minutes checked through the last cycle cutoff or terminal decision |
| `BACKFILL` | A page committed, but more closed minutes remain |
| `GAP` | Failed/incomplete history or ambiguous deadline; cursor retained |
| `UNVERIFIED` | Legacy, direct-import or manually overridden history requires reconciliation |
| `UNSUPPORTED` | No correct history feed for this exchange/market type |

Backfill, gaps, unsupported markets and unverified open signals contribute
bounded error codes to lifecycle cycle diagnostics. The cycle is `PARTIAL`
and the existing runtime health endpoint does not advertise `OK`. A normal
wait for the current minute to close is not an error. Network failures retain
their timeout/connection diagnostic classes.

## Validation and rollout

Regression tests cover outages beyond the old window, LONG/SHORT early stops,
pagination across restarts, price updates not advancing the cursor, gaps and
invalid prices, expiry behind backfill, creation/expiry boundaries, rollback
of events/outbox/cursor, retries, operator races and legacy migration behavior.
CI additionally runs two concurrent workers against PostgreSQL in an isolated
temporary schema, verifying one set of transitions and deliveries.

This patch is for a draft PR into `feature/tradinggpt-core-v3`. Do not deploy
before reviewing the migration, held open/manual signals, closed-minute
latency and CI result. Backend code requires the new migration; merely
switching a bind-mounted checkout is **not** a deployment procedure. Deployment
must coordinate API stop/start and migration separately after approval.
Downgrade removes progress metadata, so subsequently upgrading cannot recover
those cursors automatically. Back up the database before an approved rollout.
