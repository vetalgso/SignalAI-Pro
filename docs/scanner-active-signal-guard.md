# Scanner active-signal guard

## Problem

The periodic scanner skips symbols with open signals before persistence. The
manual `/api/v3/signals/scan` endpoint calls the generator directly. Its exact
fingerprint includes price levels and the generated hour, so small level drift
or a later hour could create another open signal for the same setup. Requests
within one scan could also repeat the same symbol with changed levels.

## Rule

`TradingSignalService.create` checks the open setup for both SCANNER and
MARKET_SCANNER as one source family, shared by manual scans, periodic scans
and direct signal creation. Scope is exchange, market type, symbol, side,
timeframe and strategy. Prices, confidence and generated hour do not open a
new scope. ACTIVE, ENTRY_REACHED, TP1_REACHED and TP2_REACHED block another
signal in that scope, even if the saved entry deadline has passed; the
tracker must record the terminal state first. Unknown/legacy history on an
open signal is not permission to create a replacement.

A duplicate returns the oldest matching signal ID through the existing
DuplicateSignalError contract. `/scan` counts it as DUPLICATE and includes
existing_signal_id, while direct POST `/signals` returns its existing 409
response. It does not update the old levels, confidence, history cursor or
status and does not create another event or Telegram outbox row.

PostgreSQL transaction advisory locks serialize cooperating creators for the
same scanner scope across both source aliases. The generator rolls back the
duplicate attempt before processing the next candidate to release the lock.
Successful creations already commit their signal, CREATED event and outbox
atomically; this rollback does not undo earlier successful candidates.
Service callers handling DuplicateSignalError must finish their transaction.

The AI_REVIEW family retains its original scope and advisory-lock namespace;
its existing tests are retained. AI and scanner are separate families, so
this is not cross-source deduplication. The broader periodic symbol prefilter
continues to operate. Other sources keep their fingerprint-only behavior.
Terminal signals allow a new setup; exact fingerprint replay remains rejected.

## Limits and rollout

No database migration or frontend change. Deploy by updating the development
checkout and restarting its bind-mounted API. All API workers must use the new
code: a worker on an older version or a direct database writer does not
participate in this application-level lock. SQLite tests exercise sequential
behavior only. The concurrency test uses the isolated PostgreSQL URL already
supplied by CI via SIGNALAI_HISTORY_TEST_DATABASE_URL.

Existing historical rows are retained. Similar SOL signals observed in a
small quality cohort motivated the audit, but their creation timestamps alone
do not prove they overlapped; this change fixes the demonstrated creation gap.
Counters continue to count stored rows. Historical deduplication, profit
accounting, break-even stops and changes to confidence/AI thresholds are outside
this change. The guard reduces repeated open recommendations; it does not
establish predictive performance.
