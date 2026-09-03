import asyncio
import json

import httpx
import pytest

from app.core.config import Settings
from app.tradinggpt.signals.ai_reviewer import (
    AIReviewError,
    OpenAICompatibleSignalReviewer,
    build_review_payload,
    candidate_ai_eligibility,
)


def settings(**updates):
    values = {
        "_env_file": None,
        "signal_ai_review_enabled": True,
        "signal_ai_api_key": "sk-test-placeholder",
    }
    values.update(updates)
    return Settings(**values)


def candidate(**updates):
    values = {
        "rejection_reason": (
            "RECOMMENDATION_CONFLICT"
        ),
        "symbol": "BNBUSDT",
        "signal_action": "LONG",
        "trade_direction": "LONG",
        "confidence": 67,
        "ranking_score": 70.22,
        "score": 78.17,
        "opportunity_score": 47.04,
        "consensus_score": 100,
        "timeframe_consensus_score": 100,
        "quality_penalty": 5,
        "candidate_age_seconds": 1,
        "risk": "high",
        "signal_levels": {
            "entry": "714.24",
            "stop_loss": "707.98",
            "take_profit": "726.74",
        },
        "warnings": ["Unconfirmed news"],
        "reasons": ["Three timeframes aligned"],
    }
    values.update(updates)
    return values


def test_strong_near_miss_is_eligible() -> None:
    assert candidate_ai_eligibility(
        candidate(),
        settings(),
    ) == (True, "ELIGIBLE")


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        (
            {"confidence": 59},
            "LOW_CONFIDENCE",
        ),
        (
            {"ranking_score": 64.99},
            "LOW_RANKING_SCORE",
        ),
        (
            {"consensus_score": 89},
            "LOW_CONSENSUS",
        ),
        (
            {"timeframe_consensus_score": 89},
            "LOW_TIMEFRAME_CONSENSUS",
        ),
        (
            {"quality_penalty": 11},
            "EXCESSIVE_QUALITY_PENALTY",
        ),
        (
            {"candidate_age_seconds": 301},
            "STALE_CANDIDATE",
        ),
        (
            {"trade_direction": "SHORT"},
            "DIRECTION_CONFLICT",
        ),
    ],
)
def test_weak_candidate_is_rejected(
    updates,
    reason,
) -> None:
    assert candidate_ai_eligibility(
        candidate(**updates),
        settings(),
    ) == (False, reason)


def test_ai_disabled_is_fail_closed() -> None:
    allowed, reason = candidate_ai_eligibility(
        candidate(),
        settings(
            signal_ai_review_enabled=False
        ),
    )

    assert allowed is False
    assert reason == "AI_REVIEW_DISABLED"


def test_payload_has_no_credentials() -> None:
    payload = build_review_payload(candidate())
    serialized = json.dumps(payload)

    assert "api_key" not in serialized
    assert "sk-" not in serialized


def test_approved_matching_direction() -> None:
    async def handler(request):
        assert (
            request.headers["Authorization"]
            == "Bearer sk-test-placeholder"
        )

        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "verdict": "APPROVE",
                                    "direction": "LONG",
                                    "confidence": 76,
                                    "rationale": (
                                        "Aligned evidence."
                                    ),
                                    "risk_flags": [
                                        "UNCONFIRMED_NEWS"
                                    ],
                                }
                            )
                        }
                    }
                ]
            },
        )

    reviewer = OpenAICompatibleSignalReviewer(
        settings(),
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(
        reviewer.review(candidate())
    )

    assert result.eligible is True
    assert result.approved is True
    assert result.reason == "AI_APPROVED"


def test_ai_cannot_change_direction() -> None:
    async def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "verdict": "APPROVE",
                                    "direction": "SHORT",
                                    "confidence": 90,
                                    "rationale": (
                                        "Opposite direction."
                                    ),
                                    "risk_flags": [],
                                }
                            )
                        }
                    }
                ]
            },
        )

    reviewer = OpenAICompatibleSignalReviewer(
        settings(),
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(
        reviewer.review(candidate())
    )

    assert result.approved is False
    assert (
        result.reason
        == "AI_DIRECTION_CHANGE_REJECTED"
    )


def test_transport_failure_is_sanitized() -> None:
    async def handler(request):
        raise httpx.ConnectError(
            "connection failed",
            request=request,
        )

    reviewer = OpenAICompatibleSignalReviewer(
        settings(),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        AIReviewError,
        match="AI Review request failed",
    ):
        asyncio.run(
            reviewer.review(candidate())
        )

def test_blocking_risk_flag_is_known() -> None:
    from app.tradinggpt.signals.ai_reviewer import (
        BLOCKING_AI_RISK_FLAGS,
    )

    assert "STALE_MARKET_DATA" in (
        BLOCKING_AI_RISK_FLAGS
    )
    assert "INVALID_LEVELS" in (
        BLOCKING_AI_RISK_FLAGS
    )
    assert "UNCONFIRMED_NEWS" not in (
        BLOCKING_AI_RISK_FLAGS
    )

def test_candidate_and_verdict_thresholds_are_separate() -> None:
    configured = settings(
        signal_ai_min_confidence=45,
        signal_ai_min_verdict_confidence=60,
    )

    eligible, reason = candidate_ai_eligibility(
        candidate(confidence=45),
        configured,
    )

    assert eligible is True
    assert reason == "ELIGIBLE"
    assert configured.signal_ai_min_confidence == 45
    assert (
        configured.signal_ai_min_verdict_confidence
        == 60
    )
