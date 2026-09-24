# Related RSS reports, not fact verification

Every RSS item currently receives `status: "unverified"`. The collector has no
primary-source verification process. Three publishers reporting a similar story
may repeat the same source. This change makes candidate matches inspectable; it
does not assign `verified`, change sentiment, scoring, news penalties, AI admission,
or scanner settings. No database migration or additional outbound request is used.

## Version 1 scope

`GET /api/v2/news` adds `related_coverage` to each article:

- `version: 1`, `method: "RSS_HEADLINE_RULES"`, `checked_at`;
- `other_publishers_count`: distinct other configured publishers, not independent
  sources or fact-checks;
- `reports`: title, publisher, canonical URL, publication time and matching basis
  (`family`, `asset`, normalized decimal `amount`, `unit`, `direction`, `shared_terms`).

Matching runs over all loaded RSS items before asset filtering and pagination, so
`limit=1` does not remove evidence links. It is recomputed on reads, using the same
60-second feed cache. Link metadata lives in that response; it is not a permanent
archive or an addition to historical signal/admission snapshots.

Both publications must have explicit timezone-bearing RSS dates within the last
24 hours. `published_at_source` distinguishes `RSS` from `FALLBACK`; the legacy
fallback display date is retained but cannot qualify as freshness evidence.
Missing provenance, missing/invalid dates, future dates and older publications do
not match. Publication time is not proof of when the underlying event happened.

Only two English headline families are recognized initially:

| Family | Required headline clues |
| --- | --- |
| `ETF_FLOW` | One recognized asset, ETF mention, same flow direction, one equal normalized dollar amount. `$1B` and `$1 billion` are equivalent. |
| `ASSET_RECOVERY` | One recognized asset, incident and recovery language, one equal amount of that asset, and a shared name-like capitalized term beyond generic words. |

Same asset alone never qualifies. Explicit conflicting weekdays, multiple assets
or amounts, recognized denial/correction/speculation language and mixed inflow /
outflow headlines are excluded. ETF options, futures, fees and recognized weekly,
monthly or annual summaries are excluded. This is a small heuristic, not semantic
understanding: it can miss valid matches or still suggest unrelated reports.
Rounded amounts, missing event dates and unrecognized qualifications remain
limitations. Compare the linked originals before drawing conclusions.

Only direct pairwise matches are returned; matches do not propagate through a
third report. Links must belong to the declared configured publisher. Tracking
parameters and fragments are removed for duplicate handling; repeats of one URL
count once, and repeats from one publisher never inflate the publisher count.
This does not establish independent ownership or original reporting.

The News panel (also used on the overview) shows the unverified label, a collapsed
list of matching reports with basis and links, and the limitation beside it.
No matches means none found by these rules in this loaded sample, not false news.
The rules intentionally do not claim coverage of all topics or languages.

## Regression examples

The supplied September 22, 2026 RSS titles are fixtures, not independently verified
article contents. The three Bitcoin ETF headlines mentioning approximately $1B
link across CoinDesk, Cointelegraph and Decrypt. The two Coldcard / 52 BTC recovery
headlines link. Other Bitcoin price, option-trade, market-cap and political stories
do not become confirmation just because they mention Bitcoin.

Tests cover opposite directions, different amounts/assets/incidents, speculative
and correction titles, old/invalid/future/fallback dates, same-publisher repeats,
tracking aliases, direct rather than transitive links, expiry of cached titles,
RSS-to-API pagination, unchanged penalties and bilingual UI link rendering.

## Rollout

Deploy backend and frontend together after PR review. This repository bind-mounts
`./backend` into the API, so restarting API loads the Python change. Rebuild and
recreate frontend. No migration is required. Old saved quality/admission records
remain unchanged, and existing news penalties continue to apply.

Read-only smoke check after rollout:

```bash
docker compose exec -T api python - <<'PY'
import json
from urllib.request import urlopen
with urlopen('http://127.0.0.1:8000/api/v2/news?asset=BTC&limit=20', timeout=30) as response:
    page = json.load(response)
print(json.dumps([{
    'title': row['title'], 'status': row['status'],
    'published_at_source': row.get('published_at_source'),
    'related_coverage': row.get('related_coverage'),
} for row in page['articles']], ensure_ascii=False, indent=2))
PY
```

Zero matches is valid, particularly once the fixture stories are older than 24
hours. Live RSS is not a deterministic acceptance fixture. Confirm version 1
metadata and the UI explanation, not a fixed positive match count.
