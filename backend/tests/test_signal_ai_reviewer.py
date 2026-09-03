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
