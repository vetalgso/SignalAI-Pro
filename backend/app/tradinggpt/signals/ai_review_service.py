from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.signal_discovery import (
    SignalScanCandidate,
)
from app.tradinggpt.signals.ai_review_repository import (
    SignalAIReviewRepository,
)
from app.tradinggpt.signals.ai_reviewer import (
    AIReviewError,
    AIReviewResult,
    OpenAICompatibleSignalReviewer,
)


TERMINAL_REVIEW_STATUSES = {
    "APPROVED",
    "REJECTED",
    "FAILED",
}


class CandidateReviewer(Protocol):
    async def review(
        self,
        candidate: dict[str, Any],
    ) -> AIReviewResult:
        ...


class SignalAIReviewService:
    def __init__(
        self,
        *,
        db: Session,
        settings: Settings,
        reviewer: CandidateReviewer | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.repository = (
            SignalAIReviewRepository(db)
        )
        self.reviewer = reviewer or (
            OpenAICompatibleSignalReviewer(
                settings
            )
        )

    def review_candidate(
        self,
        candidate_id: int,
    ) -> dict[str, Any]:
        candidate = self.db.get(
            SignalScanCandidate,
            candidate_id,
        )

        if candidate is None:
            return {
                "action": "NOT_FOUND",
                "candidate_id": candidate_id,
            }

        payload = self._candidate_payload(
            candidate
        )

        review, created = (
            self.repository.create_pending(
                candidate_id=candidate.id,
                provider=(
                    self.settings
                    .signal_ai_provider
                ),
                model=(
                    self.settings
                    .signal_ai_model
                ),
                requested_direction=str(
                    candidate.signal_action or ""
                ),
            )
        )

        if (
            not created
            and review.status
            in TERMINAL_REVIEW_STATUSES
        ):
            return {
                "action": "ALREADY_REVIEWED",
                "review": review.safe_summary(),
            }

        if (
            not created
            and review.status == "PROCESSING"
        ):
            return {
                "action": "ALREADY_PROCESSING",
                "review": review.safe_summary(),
            }

        self.repository.mark_processing(
            review
        )

        try:
            result = asyncio.run(
                self.reviewer.review(payload)
            )
        except AIReviewError:
            failed = self.repository.fail(
                review,
                error_code="PROVIDER_ERROR",
            )
            return {
                "action": "FAILED",
                "review": failed.safe_summary(),
            }
        except Exception:
            failed = self.repository.fail(
                review,
                error_code="INTERNAL_ERROR",
            )
            return {
                "action": "FAILED",
                "review": failed.safe_summary(),
            }

        completed = self.repository.complete(
            review,
            result,
        )

        return {
            "action": completed.status,
            "review": completed.safe_summary(),
        }

    @staticmethod
    def _candidate_payload(
        candidate: SignalScanCandidate,
    ) -> dict[str, Any]:
        snapshot = (
            dict(candidate.snapshot)
            if isinstance(
                candidate.snapshot,
                dict,
            )
            else {}
        )

        created_at = candidate.created_at

        if created_at.tzinfo is None:
            created_at = created_at.replace(
                tzinfo=timezone.utc
            )

        candidate_age_seconds = max(
            0.0,
            (
                datetime.now(timezone.utc)
                - created_at
            ).total_seconds(),
        )

        snapshot.update(
            {
                "candidate_id": candidate.id,
                "candidate_age_seconds": (
                    candidate_age_seconds
                ),
                "rejection_reason": (
                    candidate.rejection_reason
                ),
                "symbol": candidate.symbol,
                "signal_action": (
                    candidate.signal_action
                ),
                "trade_direction": (
                    candidate.trade_direction
                ),
                "confidence": (
                    float(candidate.confidence)
                    if candidate.confidence
                    is not None
                    else None
                ),
                "ranking_score": (
                    float(candidate.ranking_score)
                    if candidate.ranking_score
                    is not None
                    else None
                ),
                "risk": candidate.risk_level,
            }
        )

        return snapshot
