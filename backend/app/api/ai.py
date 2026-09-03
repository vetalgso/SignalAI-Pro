from fastapi import APIRouter

from app.core.config import settings


router = APIRouter(prefix="/ai", tags=["AI"])


@router.get("/status")
def ai_status() -> dict[str, object]:
    configured = bool(
        settings.signal_ai_api_key.strip()
    )
    enabled = (
        settings.signal_ai_review_enabled
        and configured
    )

    return {
        "configured": configured,
        "enabled": enabled,
        "status": (
            "enabled"
            if enabled
            else (
                "ready"
                if configured
                else "not_configured"
            )
        ),
        "provider": settings.signal_ai_provider,
        "model": settings.signal_ai_model,
        "review_policy": {
            "max_candidates": (
                settings.signal_ai_max_candidates
            ),
            "minimum_confidence": (
                settings.signal_ai_min_confidence
            ),
            "minimum_ranking_score": (
                settings.signal_ai_min_ranking_score
            ),
            "minimum_consensus_score": (
                settings.signal_ai_min_consensus_score
            ),
            "minimum_timeframe_score": (
                settings.signal_ai_min_timeframe_score
            ),
            "maximum_quality_penalty": (
                settings.signal_ai_max_quality_penalty
            ),
            "maximum_candidate_age_seconds": (
                settings
                .signal_ai_max_candidate_age_seconds
            ),
        },
        "message": (
            "AI review is active."
            if enabled
            else (
                "AI credentials are configured; "
                "review activation is pending."
                if configured
                else "AI credentials are not configured."
            )
        ),
    }
