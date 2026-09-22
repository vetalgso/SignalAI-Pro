"""Capture the first rule used by the existing asset-risk policy."""
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, Field, FiniteFloat, ValidationError


class RiskHorizon(BaseModel):
    horizon_minutes: int | None = Field(default=None, gt=0)
    level: str


class RiskAssessment(BaseModel):
    version: Literal[1] = 1
    calculated_at: AwareDatetime
    level: str
    profile_risk: str
    reason: Literal["FORECAST_HIGH", "MULTIPLE_ELEVATED", "PROFILE_WITH_ELEVATED",
                    "INVALID_VOLUME", "SIGNAL_WARNINGS", "LOW_VOLUME", "PROFILE"]
    horizons: list[RiskHorizon]
    signal_available: bool
    warning_count: int = Field(ge=0)
    volume_state: Literal["AVAILABLE", "MISSING", "INVALID", "NONFINITE"]
    volume_ratio: FiniteFloat | None


def assess_risk(signal: dict[str, Any] | None, forecast: dict[str, Any] | None,
                profile_risk: str) -> RiskAssessment:
    items = forecast.get("forecasts", []) if forecast else []
    risks = [item.get("risk_level", "normal") for item in items]
    horizons = []
    for item, risk in zip(items, risks):
        try:
            minutes = int(item.get("horizon_minutes", 0))
        except (TypeError, ValueError, OverflowError):
            minutes = 0
        horizons.append(RiskHorizon(horizon_minutes=minutes if minutes > 0 else None,
                                    level=str(risk)))
    decision = signal.get("decision") if signal else None
    warnings = decision.get("warnings", []) if isinstance(decision, dict) else []
    indicators = signal.get("indicators") if signal else None
    volume = indicators.get("volume") if isinstance(indicators, dict) else None
    raw_ratio = volume.get("ratio") if isinstance(volume, dict) else None
    ratio = None
    invalid = False
    volume_state = "MISSING" if raw_ratio is None else "INVALID"
    try:
        ratio = float(raw_ratio)
        invalid = ratio != ratio
        volume_state = "AVAILABLE" if isfinite(ratio) else "NONFINITE"
    except (TypeError, ValueError):
        invalid = True

    # Keep the original order and comparisons, including infinity handling.
    level, reason = profile_risk, "PROFILE"
    if "high" in risks:
        level, reason = "high", "FORECAST_HIGH"
    elif risks.count("elevated") >= 2:
        level, reason = "high", "MULTIPLE_ELEVATED"
    elif risks.count("elevated") == 1 and profile_risk == "high":
        level, reason = "high", "PROFILE_WITH_ELEVATED"
    elif signal and invalid:
        level, reason = "high", "INVALID_VOLUME"
    elif signal and len(warnings) >= 2:
        level, reason = "high", "SIGNAL_WARNINGS"
    elif signal and ratio < 0.25:
        level, reason = "high", "LOW_VOLUME"

    return RiskAssessment(
        calculated_at=datetime.now(timezone.utc), level=level, profile_risk=profile_risk,
        reason=reason, horizons=horizons, signal_available=bool(signal),
        warning_count=len(warnings), volume_state=volume_state,
        volume_ratio=ratio if ratio is not None and isfinite(ratio) else None,
    )


def read_risk_assessment(snapshot: object, risk_level: str | None) -> RiskAssessment | None:
    if not isinstance(snapshot, dict):
        return None
    raw = snapshot.get("risk_assessment")
    if not isinstance(raw, dict) or raw.get("version") != 1:
        return None
    try:
        result = RiskAssessment.model_validate(raw)
    except ValidationError:
        return None
    if result.level.upper() != str(risk_level or "").upper():
        return None
    if result.reason != "PROFILE" and result.level != "high":
        return None
    if result.reason == "PROFILE" and result.level != result.profile_risk:
        return None
    return result
