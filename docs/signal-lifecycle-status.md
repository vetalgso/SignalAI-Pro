# Signal tracking status

GET /api/v3/signals/runtime/lifecycle exposes a read-only projection of
signal_lifecycle_cycles. No additional migration or execution setting is needed.
It uses the existing journal introduced by 20260909_0021.

The API selects the latest finished COMPLETED/PARTIAL/FAILED/CANCELLED cycle
by completed_at DESC, id DESC, across all workers. RUNNING rows do not replace
the last completion. It does not determine whether an individual worker is alive.
Worker IDs, raw error dictionaries and exception messages are not exposed.
Database errors fail the request rather than returning a healthy empty result.

State precedence:

1. DISABLED when tracking is configured off; saved history remains visible.
2. WAITING when enabled with no finished cycles.
3. STALE when completion age exceeds max(3 * configured interval, 180 seconds).
4. ERRORS for PARTIAL/FAILED/CANCELLED or a nonzero error count.
5. UNKNOWN for COMPLETED with no recorded error count.
6. OK for a fresh COMPLETED cycle with zero recorded errors.

Null durations and counts remain unknown, represented by a dash in the UI.
A successful check with zero tracked signals is valid and is not an error.
Timestamps are UTC in the API and displayed in the browser's local timezone.
Future completion timestamps are clamped to zero age, matching the metrics.

The card appears above the signal counters and refreshes via GET every 30 seconds
after the previous request completes. Each request has an eight-second timeout.
Manual refresh does not invoke tracking, scanning or trading. Requests and timers
are cancelled on unmount. Failed refreshes clear the old successful display.
Age advances locally using elapsed browser time. If the last response is older
than 90 seconds, the card labels it as out-of-date instead of keeping OK visible.

UI STALE is shown immediately at the age threshold. The Prometheus stale alert
has an additional one-minute pending period. Neither state is proof of execution
or investment performance. One completed worker does not certify all workers.

Verification: backend/tests/test_signal_lifecycle_read.py, full backend regression,
and npm --prefix frontend run build. UI checks: RU/EN, narrow viewport, empty journal,
disabled tracking with history, errors, request failure and recovery.
