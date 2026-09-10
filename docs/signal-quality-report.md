# Signal quality report

GET `/api/v3/signals/quality` is read-only. Parameters: `days` 1–365
(default 30), `source` AI_REVIEW/SCANNER/ALL (default AI_REVIEW),
`transition_origin` ALL/AUTOMATIC/MANUAL/UNKNOWN (default ALL), `limit`
1–100 (default 25), `offset` >= 0. The UI offers 7/30/90/365 days.

The cohort is signals whose `generated_at` falls inclusively between
`as_of - days` and `as_of`, in UTC. Results reflect recorded lifecycle
state when the report is read, not events occurring exclusively inside
that date range. Recent cohorts still have unresolved signals.

Groups preserve source, exchange, market type, symbol, side, timeframe
and strategy. Summary counts include all groups, not just the page.

The transition-origin filter selects signals before computing summary,
groups and pagination, together with the existing period and source filters.
The response echoes `transition_origin`. Classification uses event types
recorded at or before `as_of`:

- `ALL`: the existing unfiltered cohort and counting behavior.
- `AUTOMATIC`: at least one `MARKET_STATUS_CHANGED`, no `STATUS_CHANGED`
  and no unrecognized event types other than `CREATED`.
- `MANUAL`: at least one `STATUS_CHANGED`, including mixed histories
  with automatic or unknown transitions.
- `UNKNOWN`: all remaining signals, including no events, creation-only
  history, and automatic transitions combined with unknown provenance.

The lifecycle tracker writes `MARKET_STATUS_CHANGED` for market transitions
and expiry; the manual status API uses the service's `STATUS_CHANGED` default.
`CREATED` does not establish automatic tracking. Neither the absence of manual
events, current signal status, entry timestamps nor payload flags establish it.
Unrecognized event types conservatively prevent an automatic classification.
Repeated events do not multiply signal counts. Automatic transitions do not
guarantee a complete history and do not confirm profitability. Historical
events are never rewritten or backfilled by this report.

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
