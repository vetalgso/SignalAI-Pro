# Saved risk and news diagnostics

For the subsequent dictionary expansion and matching rules, see
[News asset coverage and matching](news-asset-matching.md). The ten-asset
coverage described below records the original diagnostics rollout.

The admission journal now explains the first rule that produced the asset risk
and separates news-dictionary coverage from RSS collection health. This is a
read-only explanation of saved scan facts, not a new admission policy.

## Risk

`ScannerResult.risk_assessment` is saved in the candidate snapshot and projected
as `items[].risk` by `/api/v3/signals/ai-admission`. The asset-analysis response
also includes it. Version 1 saves calculation time, profile, resulting risk,
first matching reason, forecast horizon levels, technical warning count and
volume availability/ratio. It does not expose provider text or raw warnings.

Rule priority is preserved:

1. Any forecast horizon marked `high`: `FORECAST_HIGH`.
2. At least two `elevated` horizons: `MULTIPLE_ELEVATED`.
3. One `elevated` horizon with the `high` profile: `PROFILE_WITH_ELEVATED`.
4. An existing technical signal with a missing/invalid/NaN volume ratio:
   `INVALID_VOLUME`.
5. At least two technical-signal warnings: `SIGNAL_WARNINGS`.
6. Volume ratio below 0.25: `LOW_VOLUME`.
7. Otherwise use the scan profile: `PROFILE`.

The forecast service's volatility rules and AI's `HIGH_RISK` rejection are
unchanged. `SIGNAL_WARNINGS` counts the technical signal's warnings, not the
quality-penalty warning list. Infinity behavior is preserved for compatibility;
non-finite diagnostic ratios serialize as null with `NONFINITE` availability.
Other factors may coexist with the first reason. Absence of a technical signal
is recorded, not automatically promoted to a new high-risk rule.

The UI expands this explanation under the `HIGH_RISK` admission reason. Other
admission reasons still identify the first unmet AI selection condition.
Legacy candidates have null risk details; the API does not recalculate them.
Malformed/version-mismatched records or a level inconsistent with the stored
candidate risk are rejected by the projection.

## News

`/api/v2/news` retains `count`, `partial` and `articles`, and adds `diagnostics`:

- `coverage`: ALL for unfiltered queries, SUPPORTED for an asset in the existing
  dictionary, UNSUPPORTED otherwise.
- `sources_state`: COMPLETE if no feed raised an error, PARTIAL if some did,
  FAILED if all configured feeds did. COMPLETE does not promise freshness,
  exhaustive coverage or independent verification of articles.
- Total/failed source counts, collected article count after deduplication, and
  matched article count before the response's limit.
- UTC `observed_at`: when this response was assembled. The existing 60-second
  shared feed cache remains in use; this is not an article publication time.

Coverage and source health are independent, so an unsupported asset and failed
sources can be reported together. A supported asset with zero matches after a
successful load means no matches in the sampled feed items, not no news anywhere.
A completely empty successful collection is represented by COMPLETE and zero
collected articles. Exceptions are never included verbatim.

The diagnostics are copied into `quality_breakdown.news.diagnostics` at analysis
time. The journal reads the saved copy. Legacy details without this optional
field remain readable and explicitly say that source diagnostics were not
recorded. If the entire news loader returns no result, diagnostics remain null;
no retrospective cause is invented.

The existing dictionary of ten assets, feed URLs, matching, scoring, cap,
thresholds and warning strings are unchanged. This update makes unsupported
coverage visible; it does not add aliases for ZEC, NEAR, CRCLB or other assets.

## Validation and rollout

Regression tests cover every risk reason, rule priority, the 0.25 boundary,
missing/non-finite data, simultaneous source and coverage problems, partial
responses with and without matches, successful empty feeds, legacy projections
and scanner -> stored snapshot -> admission response round trips. Component
render tests cover Russian/English, legacy unknowns and independent news states.

No migration or historical backfill is needed. After review and merge, update
the API and rebuild the frontend. New regular scans capture details; old scans,
including run 456, keep their original unknown risk/source diagnostics. No manual
scan, AI request, threshold change or historical replay is part of this rollout.
Browser layout still needs verification in the deployed app.
