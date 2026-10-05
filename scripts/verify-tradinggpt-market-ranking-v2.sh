#!/usr/bin/env bash

set -euo pipefail

docker compose exec -T api python - <<'PY'
from app.tradinggpt.scoring import ScoringEngine


strong_aligned = ScoringEngine.ranking_score(
    opportunity_score=85,
    consensus_score=95,
    confidence=90,
)

strong_conflicted = ScoringEngine.ranking_score(
    opportunity_score=85,
    consensus_score=30,
    confidence=90,
)

moderate_aligned = ScoringEngine.ranking_score(
    opportunity_score=70,
    consensus_score=95,
    confidence=85,
)

weak = ScoringEngine.ranking_score(
    opportunity_score=30,
    consensus_score=40,
    confidence=45,
)


assert round(strong_aligned, 2) == 88.25
assert round(strong_conflicted, 2) == 72.00
assert round(moderate_aligned, 2) == 78.50

assert strong_aligned > moderate_aligned
assert moderate_aligned > strong_conflicted
assert strong_conflicted > weak


assert ScoringEngine.ranking_score(
    opportunity_score=200,
    consensus_score=200,
    confidence=200,
) == 100.0

assert ScoringEngine.ranking_score(
    opportunity_score=-50,
    consensus_score=-50,
    confidence=-50,
) == 0.0


print("TradingGPT Market Ranking v2 verification passed")
print(
    {
        "strong_aligned": round(strong_aligned, 2),
        "moderate_aligned": round(moderate_aligned, 2),
        "strong_conflicted": round(strong_conflicted, 2),
        "weak": round(weak, 2),
    }
)
PY
