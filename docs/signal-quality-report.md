# Signal quality report

GET `/api/v3/signals/quality` is read-only. Parameters: `days` 1–365
(default 30), `source` AI_REVIEW/SCANNER/ALL (default AI_REVIEW), `limit`
1–100 (default 25), `offset` >= 0. The UI offers 7/30/90/365 days.

The cohort is signals whose `generated_at` falls inclusively between
`as_of - days` and `as_of`, in UTC. Results reflect recorded lifecycle
state when the report is read, not events occurring exclusively inside
that date range. Recent cohorts still have unresolved signals.

Groups preserve source, exchange, market type, symbol, side, timeframe
and strategy. Summary counts include all groups, not just the page.

- `total`: number of distinct signal rows, including historical duplicates.
- `open`: ACTIVE, ENTRY_REACHED, TP1_REACHED, TP2_REACHED.
- `terminal`: TP3_REACHED, STOPPED, EXPIRED, CANCELLED.
- `unknown_status`: all other current statuses.
- `entered`: recorded ENTRY_REACHED event or `entry_reached_at` <= as_of.
- `tp1`, `tp2`, `tp3`: distinct signals with an explicit event to that
  target status. Both automatic and manual transitions count; repeated
  events count once. TP3 does not imply TP2, which may be absent.
- `stopped`, `expired`, `cancelled`: current terminal status counts.
- `without_events`: signals without event rows recorded by as_of.
- `manual_transitions`: signals with a STATUS_CHANGED event by as_of.

TP achievements remain counted after a later stop. Milestone columns
overlap and must not be added together as exclusive outcomes. Missing
events are not reconstructed from prices or the current TP status.
No win rate, executed PnL, fees, slippage or profitability claim is
derived from these counts. The existing lifecycle engine decides
ambiguous candles (stop before target); this report does not resimulate
market data or change those rules. Historical duplicates are not deleted.

No migrations, background tasks, order execution, promotion or external
market/provider requests are performed by the endpoint.
