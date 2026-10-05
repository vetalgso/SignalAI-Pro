# Signal lifecycle cycle journal

Migration `20260909_0021` adds `signal_lifecycle_cycles`. The background
`refresh_product_signals` wrapper commits a RUNNING row before invoking
the existing tracker. Manual `/signals/refresh` requests are outside this
journal's scope. The tracker and its trading rules are unchanged.

Fields: worker UUID (one per imported worker process), start/end UTC,
monotonic duration in seconds, configured poll interval, checked signals,
updated signals, transition count, price updates, error count and bounded
error-code counts. A cycle starts after the preceding cycle completes
and its configured wait elapses; the interval is not a hard deadline.

Statuses:

- RUNNING: start persisted, no completion recorded yet.
- COMPLETED: tracker returned its counters with no errors.
- PARTIAL: tracker returned one or more per-symbol/per-signal errors.
- FAILED: uncaught cycle exception or malformed tracker result.
- CANCELLED: asyncio cancellation was caught and recorded, then re-raised.

RUNNING does not prove an orphan: the cycle may still run, the process
may have stopped abruptly, or the completion write may have failed.
New workers do not modify existing RUNNING rows. No heartbeat or automatic
cross-worker recovery is introduced. Null counters on RUNNING/failed
cycles mean unknown, not zero. Transitions committed before a cycle
exception remain committed and must be inspected in signal event history.

Journal transactions use separate sessions. SQLAlchemy journal failures
log only JOURNAL_WRITE_FAILED and do not prevent tracking or roll back
committed signal work. If the database cannot record a start, that cycle
has no journal row. This is best-effort observability, not an exactly-once
audit or evidence of continuous uptime.

Error codes: UPSTREAM_TIMEOUT, UPSTREAM_CONNECTION_ERROR,
MARKET_DATA_ERROR, DATABASE_ERROR, INVALID_LIFECYCLE_DATA, UNKNOWN_ERROR,
INVALID_CYCLE_RESULT, CYCLE_CANCELLED. MarketDataError is recorded as such;
its hidden root cause is not inferred. No raw exception message, traceback,
symbol, signal ID, provider payload or credentials are persisted here.
The outer background loop also logs a bounded code instead of traceback.

At a 60-second wait this can add roughly 1,440 rows/day per continuously
running worker (fewer for long cycles). No automatic purge is included.
Retention should be chosen before long-term operation. Indexes support
start-time and status inspection. Downgrade deletes only this journal
table and its indexes, including its historical diagnostics.

Read-only inspection:

```sql
SELECT id, worker_id, status, started_at, completed_at, duration_seconds,
       poll_interval_seconds, checked_signals, updated_signals,
       transition_count, price_updates, error_count, error_counts
FROM signal_lifecycle_cycles
ORDER BY id DESC LIMIT 20;
```

No historical reconstruction of the September 7 delay is possible from
this new journal. This change records future background cycles only.
