from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from app.core.config import Settings


class AIReviewError(RuntimeError):
    """Safe AI Review failure without credential disclosure."""


class AIReviewVerdict(BaseModel):
    verdict: Literal["APPROVE", "REJECT"]
    direction: Literal["LONG", "SHORT"]
    confidence: int = Field(ge=0, le=100)
    rationale: str = Field(
        min_length=1,
        max_length=600,
    )
    risk_flags: list[str] = Field(
        default_factory=list,
        max_length=8,
    )


class AIReviewResult(BaseModel):
    eligible: bool
    approved: bool
    reason: str
    verdict: AIReviewVerdict | None = None


def decimal_value(
    value: object,
) -> Decimal | None:
    if value is None:
        return None

    try:
        return Decimal(str(value))
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        return None


def candidate_ai_eligibility(
    candidate: dict[str, Any],
    settings: Settings,
) -> tuple[bool, str]:
    if not settings.signal_ai_review_enabled:
        return False, "AI_REVIEW_DISABLED"

    if not settings.signal_ai_api_key.strip():
        return False, "AI_NOT_CONFIGURED"

    if (
        str(candidate.get("rejection_reason", "")).upper()
        != "RECOMMENDATION_CONFLICT"
    ):
        return False, "UNSUPPORTED_REJECTION_REASON"

    action = str(
        candidate.get("signal_action", "")
    ).upper()
    direction = str(
        candidate.get("trade_direction", "")
    ).upper()

    if action not in {"LONG", "SHORT"}:
        return False, "NO_ACTIONABLE_DIRECTION"

    if action != direction:
        return False, "DIRECTION_CONFLICT"

    confidence = decimal_value(
        candidate.get("confidence")
    )
    ranking = decimal_value(
        candidate.get("ranking_score")
    )
    consensus = decimal_value(
        candidate.get("consensus_score")
    )
    timeframe = decimal_value(
        candidate.get("timeframe_consensus_score")
    )
    quality_penalty = decimal_value(
        candidate.get("quality_penalty")
    )

    required = {
        "confidence": confidence,
        "ranking_score": ranking,
        "consensus_score": consensus,
        "timeframe_consensus_score": timeframe,
        "quality_penalty": quality_penalty,
    }

    if any(
        value is None
        for value in required.values()
    ):
        return False, "INCOMPLETE_CANDIDATE"

    assert confidence is not None
    assert ranking is not None
    assert consensus is not None
    assert timeframe is not None
    assert quality_penalty is not None

    if confidence < Decimal(
        str(settings.signal_ai_min_confidence)
    ):
        return False, "LOW_CONFIDENCE"

    if ranking < Decimal(
        str(settings.signal_ai_min_ranking_score)
    ):
        return False, "LOW_RANKING_SCORE"

    if consensus < Decimal(
        str(settings.signal_ai_min_consensus_score)
    ):
        return False, "LOW_CONSENSUS"

    if timeframe < Decimal(
        str(settings.signal_ai_min_timeframe_score)
    ):
        return False, "LOW_TIMEFRAME_CONSENSUS"

    if quality_penalty > Decimal(
        str(settings.signal_ai_max_quality_penalty)
    ):
        return False, "EXCESSIVE_QUALITY_PENALTY"

    levels = candidate.get("signal_levels")

    if not isinstance(levels, dict):
        return False, "LEVELS_UNAVAILABLE"

    if not {
        "entry",
        "stop_loss",
        "take_profit",
    }.issubset(levels):
        return False, "LEVELS_UNAVAILABLE"

    entry = decimal_value(levels.get("entry"))
    stop_loss = decimal_value(
        levels.get("stop_loss")
    )
    take_profit = decimal_value(
        levels.get("take_profit")
    )

    if (
        entry is None
        or stop_loss is None
        or take_profit is None
        or entry <= 0
        or stop_loss <= 0
        or take_profit <= 0
    ):
        return False, "INVALID_LEVELS"

    if action == "LONG" and not (
        stop_loss < entry < take_profit
    ):
        return False, "INVALID_LEVEL_DIRECTION"

    if action == "SHORT" and not (
        take_profit < entry < stop_loss
    ):
        return False, "INVALID_LEVEL_DIRECTION"

    return True, "ELIGIBLE"


def build_review_payload(
    candidate: dict[str, Any],
) -> dict[str, Any]:
    allowed_fields = (
        "symbol",
        "signal_action",
        "trade_direction",
        "confidence",
        "ranking_score",
        "score",
        "opportunity_score",
        "consensus_score",
        "timeframe_consensus_score",
        "timeframe_directions",
        "trend_direction",
        "trade_style",
        "risk",
        "quality_penalty",
        "warnings",
        "reasons",
        "market_price",
        "signal_strategy",
        "signal_levels",
    )

    return {
        name: candidate.get(name)
        for name in allowed_fields
    }


class OpenAICompatibleSignalReviewer:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport
        | httpx.BaseTransport
        | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport

    async def review(
        self,
        candidate: dict[str, Any],
    ) -> AIReviewResult:
        eligible, reason = candidate_ai_eligibility(
            candidate,
            self.settings,
        )

        if not eligible:
            return AIReviewResult(
                eligible=False,
                approved=False,
                reason=reason,
            )

        action = str(
            candidate["signal_action"]
        ).upper()

        payload = self._request_payload(
            candidate
        )

        try:
            async with httpx.AsyncClient(
                base_url=(
                    self.settings.signal_ai_base_url
                    .rstrip("/")
                    + "/"
                ),
                timeout=(
                    self.settings
                    .signal_ai_timeout_seconds
                ),
                transport=self.transport,
                headers={
                    "Authorization": (
                        "Bearer "
                        + self.settings
                        .signal_ai_api_key
                    ),
                    "Content-Type": (
                        "application/json"
                    ),
                },
            ) as client:
                response = await client.post(
                    "chat/completions",
                    json=payload,
                )
                response.raise_for_status()
                verdict = self._parse_response(
                    response.json()
                )
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise AIReviewError(
                "AI Review request failed"
            ) from exc

        if verdict.direction != action:
            return AIReviewResult(
                eligible=True,
                approved=False,
                reason="AI_DIRECTION_CHANGE_REJECTED",
                verdict=verdict,
            )

        if verdict.verdict != "APPROVE":
            return AIReviewResult(
                eligible=True,
                approved=False,
                reason="AI_REJECTED",
                verdict=verdict,
            )

        if verdict.confidence < int(
            self.settings.signal_ai_min_confidence
        ):
            return AIReviewResult(
                eligible=True,
                approved=False,
                reason="AI_LOW_CONFIDENCE",
                verdict=verdict,
            )

        return AIReviewResult(
            eligible=True,
            approved=True,
            reason="AI_APPROVED",
            verdict=verdict,
        )

    def _request_payload(
        self,
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        system_prompt = (
            "You are the second-stage risk reviewer "
            "for a cryptocurrency signal scanner. "
            "Review only the supplied candidate. "
            "Never change its LONG/SHORT direction. "
            "Reject when evidence is insufficient, "
            "contradictory, stale, or risk is excessive. "
            "Do not execute trades and do not suggest "
            "position size. Return only schema-valid JSON."
        )

        return {
            "model": self.settings.signal_ai_model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        build_review_payload(candidate),
                        ensure_ascii=False,
                        separators=(",", ":"),
                        default=str,
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "signal_ai_review",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "verdict": {
                                "type": "string",
                                "enum": [
                                    "APPROVE",
                                    "REJECT",
                                ],
                            },
                            "direction": {
                                "type": "string",
                                "enum": [
                                    "LONG",
                                    "SHORT",
                                ],
                            },
                            "confidence": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 100,
                            },
                            "rationale": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 600,
                            },
                            "risk_flags": {
                                "type": "array",
                                "maxItems": 8,
                                "items": {
                                    "type": "string",
                                },
                            },
                        },
                        "required": [
                            "verdict",
                            "direction",
                            "confidence",
                            "rationale",
                            "risk_flags",
                        ],
                    },
                },
            },
        }

    @staticmethod
    def _parse_response(
        response: dict[str, Any],
    ) -> AIReviewVerdict:
        choices = response["choices"]

        if not isinstance(choices, list) or not choices:
            raise ValueError("Missing AI choices")

        message = choices[0]["message"]
        content = message["content"]

        if not isinstance(content, str):
            raise ValueError(
                "Invalid AI message content"
            )

        return AIReviewVerdict.model_validate_json(
            content
        )
