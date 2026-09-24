# AI admission journal

The Signals page now shows **AI review admission** before the existing AI review
journal. It answers why a scanner candidate did not reach an AI request.

## Meaning

Only candidates with `RECOMMENDATION_CONFLICT` enter the existing AI preselection
path. They have a technical LONG/SHORT direction that conflicts with the final
recommendation (often WAIT). Other scanner rejection reasons remain outside this
journal; the header distinguishes all scanned assets from these candidates.

For each candidate evaluated by `SignalAIReviewService.review_scan_run`, the
service saves `snapshot.ai_admission` (version 1):

- `action`: SELECTED or SKIPPED;
- `reason`: first failed eligibility condition, HIGH_RISK, BATCH_LIMIT, or ELIGIBLE;
- `confidence` and the configured `minimum_confidence` at evaluation time;
- actual `candidate_age_seconds`, configured `max_candidates`, and UTC `evaluated_at`.

Confidence is the scanner's system score, not the AI verdict score and not an
estimated probability of profit. A confidence threshold is shown even if another
condition failed first. The journal does not claim all other conditions passed.

The existing eligibility function, thresholds, ranking order and batch limit
remain in use. A candidate can pass all eligibility checks but be skipped for
HIGH_RISK or because higher-ranked candidates filled the AI batch limit.
SELECTED means selected for review, not that an AI request succeeded or a signal
was created. The existing review journal reports those later outcomes.

The whole preselection is committed before provider requests. A failed commit
rolls back and raises; no AI calls follow. Other candidate snapshot fields,
including promotion records, are preserved. Explicitly evaluating the same scan
again replaces its admission record with the latest evaluation, including the
new timestamp and threshold. The normal background loop evaluates each new scan.

## API

`GET /api/v3/signals/ai-admission?limit=25&offset=0` returns the latest scan.
`run_id=<id>` pins a specific scan; the frontend pins pagination and resets to the
latest scan only on refresh. Limits: 1–100, offset >= 0, run_id >= 1. A missing
explicit scan returns 404. No scans returns a successful empty page.

The response includes `run`, paginated `items`, `total`, `limit`, `offset`,
`reason_counts`, and `not_recorded_count`. Counts cover all recommendation-conflict
candidates in the selected scan, independently of pagination. Each row contains
`candidate_id`, `symbol`, and a nullable `decision` with only allowlisted fields.
No raw snapshot, credentials, provider payload or exception message is exposed.
Reads do not invoke AI, evaluate conditions, create reviews/signals or write data.

Missing, unsupported-version or malformed records return `decision: null`, shown
as “Not recorded”. They are never interpreted as a rejection. This covers old
scans, a disabled AI background path, and the interval between saving the scan
and committing its preselection. Refresh can reveal a newly completed selection.
Historical decisions are not reconstructed using today's settings or candidate age.

## Deployment and validation

No database migration or data backfill is required. New records appear after the
updated backend completes a normal scan with AI review enabled. Deploy the API
and rebuild the frontend together after PR review; frontend-only deployment
against the old backend displays a load error, not an empty success.

Validation includes backend tests for rejection persistence without provider
calls, ranking/batch limits, actual age, snapshot preservation, transaction
failure, safe projection, pagination and legacy records. Frontend request tests
cover scan pinning, mismatched responses, errors and cancellation.
Existing PostgreSQL concurrency coverage for lifecycle history still runs in CI;
this feature does not change signal lifecycle or existing history.

## Quality penalty breakdown

New scanner candidates also save `snapshot.quality_breakdown` version 1, captured
from the same inputs used to calculate the penalty. The asset-analysis response
and market-scan response expose this same structure. Existing component functions
and their numeric thresholds remain unchanged, as do the 30-point total cap,
confidence deduction, candidate ranking, and AI eligibility checks.

The structure records:

- UTC calculation time;
- forecast component points, data availability, uncertainty/sideways count, and
  the original status for every supplied horizon (including the 2-day horizon);
- volume component points, missing/invalid/available state and finite volume ratio;
- news component points, missing/available state, article count and count without
  the exact `verified` status;
- sum before the cap, cap, and final penalty.

Warnings now report counts instead of claiming a majority for any positive
penalty. Missing volume or news is distinguished from observed low volume or
unverified articles. These clearer warning strings also flow into the existing
AI payload; model wording can change even though numeric gates are unchanged.
No raw news articles, credentials or provider messages are added to the journal.

`AdmissionDecision.maximum_quality_penalty` saves the configured AI maximum at
preselection time. It is nullable for older records. It is different from the
30-point calculation cap. For example, component points 15 + 15 + 10 sum to 40,
are capped at 30, and exceed a saved AI maximum of 20.

The admission endpoint adds nullable `items[].quality`, validated from the stored
snapshot. Invalid versions, inconsistent component totals/counts, or a mismatch
with the candidate's saved `quality_penalty` return null. Reads never recalculate
historical details or substitute today's threshold. No database migration is
needed. Older candidates, including scan 433, remain without a saved breakdown.

The new expandable Quality penalty cell displays the components, availability,
raw forecast statuses and saved AI maximum. Raw UP/DOWN/SIDEWAYS/UNCERTAIN statuses
are distinct from derived LONG/SHORT timeframe labels. They are not rewritten to
make these two different calculations appear identical. Component tests render
Russian/English states, capped totals, missing data, legacy records and zero
values. Desktop/mobile browser layout still needs visual verification at rollout.
