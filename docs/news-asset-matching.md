# News asset coverage and matching

The news dictionary expands from 10 to 38 assets, including all 20 assets in
`FALLBACK_ASSETS` and additional assets observed in scanner runs. This remains a
curated catalog, not a promise to cover every asset in the dynamic Binance
universe. Unknown assets retain `coverage: UNSUPPORTED`.

## Catalog

BTC, ETH, BNB, SOL, XRP, ADA, DOGE, TRX, AVAX, LINK, SUI, TON, DOT, LTC, BCH,
NEAR, APT, UNI, AAVE, ATOM, ZEC, ENA, STRK, ARB, ONE, PROVE, BANK, TAO, WLD,
XLM, PAXG, FET, ONDO, SAGA, TRUMP, PUMP, MUBARAK, CRCLB.

The rules live in `backend/app/news/assets.py`; `ASSETS` remains importable from
`app.news.service` for existing diagnostics. Names identify a project or asset,
not a claim that every article mentioning it concerns a particular trade.

## Matching policy

- Match curated project names with Unicode word boundaries, without requiring
  uppercase text. Full names such as Litecoin, Bitcoin Cash, NEAR Protocol,
  Chainlink, Lorenzo Protocol and Succinct Network are distinct rules.
- Accept exact `$TICKER` and USDT/USDC trading-pair notation for supported assets.
  Longer tokens such as `$TRUMPOTHER` or `MYNEARUSDT` do not match.
- Accept bare case-insensitive tickers only outside the guarded set. Common
  words/names such as NEAR, ONE, BANK, LINK, DOT, PUMP, SAGA and TRUMP are guarded.
- Most guarded tickers also accept an uppercase ticker immediately adjacent to
  `token`, `memecoin` or `meme coin`. Lowercase prose such as `one token` and
  `near token launch` is not enough. BANK requires a project name or explicit
  ticker/pair, because even `bank token` is ambiguous.
- TRUMP additionally accepts explicit `Official Trump token/memecoin`,
  `Trump memecoin` and possessive `Trump's memecoin` phrases. Political mentions
  and `#TRUMP` alone are insufficient. PUMP accepts `Pump.fun token`, not a generic
  pump in prices. MUBARAK accepts a named token/memecoin phrase, not a greeting.
- CRCLB accepts its exact ticker/pair and tokenized bStocks product name.
  `Circle`, `Circle Internet Group`, `USDC` and the equity ticker `CRCL` alone do
  not imply CRCLB. News about an underlying issuer is not automatically assigned
  to every tokenized instrument referencing it.
- Bitcoin Cash/SV/Gold/ABC names do not independently tag BTC. Ethereum Classic
  does not independently tag ETH. A separate explicit BTC/ETH mention in the
  same article can still match.
- Match visible text in title and description separately. A phrase cannot cross
  that boundary. Decode HTML entities, normalize whitespace, ignore script/style
  content, HTML attributes and URL paths. One asset is emitted once per article.

These rules favor precision over recall. Bare guarded tickers in price lists,
misspellings, translations and unlisted aliases may be missed. This is a
rule-based matcher, not a general entity resolver or a guarantee against every
ambiguous sentence. Adding another asset requires positive and negative cases.

## Compatibility and behavioral impact

Existing `count`, `partial`, `articles`, IDs, RSS URLs, feed limits, shared cache,
sorting and `unverified` article status remain. Diagnostics add optional
`matcher_version`, set to 1 by the new service and saved in quality snapshots.
Legacy diagnostics without it still load as null; old candidate snapshots are
not re-tagged or backfilled.

Scoring formulas, quality penalties, risk policy and AI thresholds are unchanged.
**Inputs do change:** correctly adding/removing article tags can change news
scores, article impact (which depends on the asset count), confidence, ranking
and which candidates reach AI. This is an intended functional correction, not
merely a diagnostic change. A supported asset with no matching article remains
empty; a matched unverified article is not promoted to verified. In the current
policy, empty news costs 5 points and fully unverified news costs 10 points, so
better coverage does not guarantee a lower penalty or more admitted candidates.
Visible-text cleanup also removes non-visible/URL text from summaries and the
sentiment input; the sentiment formula itself is unchanged.

## Mapping references

Reviewed 2026-09-22. These primary sources anchor the less obvious naming
choices; matching rules remain local and do not fetch them at runtime.

- TRUMP: https://gettrumpmemes.com/
- CRCLB: https://www.binance.com/en-ZA/how-to-buy/circle-internet-group-tokenized-bstocks
- PROVE: https://www.binance.com/en/academy/articles/what-is-succinct-prove
- BANK: https://www.binance.com/en/academy/articles/what-is-lorenzo-protocol-bank
- NEAR: https://near.org/

## Validation and rollout

Tests cover all catalog assets with named/explicit positive examples; ordinary
words, political titles, company/equity mentions, longer substrings and hidden
HTML/URLs with negative examples; and real RSS parsing -> filtering -> saved
quality diagnostics. Existing source-failure tests now use UNLISTED rather than
newly supported assets. The shared-cache test remains unchanged.

Backend-only change, no migration or frontend rebuild required. After CI and
merge, update the checkout and restart the API. A normal new scan will record
new coverage/matches; the already deployed UI can display them. Do not judge old
runs by the new dictionary. No manual scan/AI request or threshold change is
part of the installation package.
