"""Persisted preselection facts; reading these never reruns eligibility checks."""
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, FiniteFloat, ValidationError, model_validator


AdmissionReason = Literal[
    "AI_REVIEW_DISABLED", "AI_NOT_CONFIGURED", "UNSUPPORTED_REJECTION_REASON",
    "NO_ACTIONABLE_DIRECTION", "DIRECTION_CONFLICT", "INVALID_TRADE_GEOMETRY",
    "STOP_DISTANCE_TOO_TIGHT", "TARGET_DISTANCE_TOO_TIGHT", "LOW_RISK_REWARD",
    "INCOMPLETE_CANDIDATE", "LOW_CONFIDENCE", "LOW_RANKING_SCORE", "LOW_CONSENSUS",
    "LOW_TIMEFRAME_CONSENSUS", "EXCESSIVE_QUALITY_PENALTY", "STALE_CANDIDATE",
    "LEVELS_UNAVAILABLE", "INVALID_LEVELS", "INVALID_LEVEL_DIRECTION",
    "HIGH_RISK", "BATCH_LIMIT", "ELIGIBLE",
]


class AdmissionDecision(BaseModel):
    version: Literal[1] = 1
    action: Literal["SELECTED", "SKIPPED"]
    reason: AdmissionReason
    confidence: FiniteFloat | None
    maximum_quality_penalty: FiniteFloat | None = Field(default=None, ge=0)
    minimum_confidence: FiniteFloat
    candidate_age_seconds: FiniteFloat = Field(ge=0)
    max_candidates: int = Field(ge=1)
    evaluated_at: AwareDatetime

    @model_validator(mode="after")
    def consistent_selection(self):
        if (self.action == "SELECTED") != (self.reason == "ELIGIBLE"):
            raise ValueError("Inconsistent admission decision")
        return self


def read_admission(snapshot: object) -> AdmissionDecision | None:
    if not isinstance(snapshot, dict):
        return None
    raw = snapshot.get("ai_admission")
    if not isinstance(raw, dict) or raw.get("version") != 1:
        return None
    try:
        return AdmissionDecision.model_validate(raw)
    except ValidationError:
        return None
