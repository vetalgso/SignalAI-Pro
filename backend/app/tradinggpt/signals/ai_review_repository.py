from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.signal_ai_review import SignalAIReview
from app.tradinggpt.signals.ai_reviewer import (
    AIReviewResult,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SignalAIReviewRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_candidate_id(
        self,
        candidate_id: int,
    ) -> SignalAIReview | None:
        return self.db.scalar(
            select(SignalAIReview).where(
                SignalAIReview.candidate_id
                == candidate_id
            )
        )

    def create_pending(
        self,
        *,
        candidate_id: int,
        provider: str,
        model: str,
        requested_direction: str,
    ) -> tuple[SignalAIReview, bool]:
        existing = self.get_by_candidate_id(
            candidate_id
        )

        if existing is not None:
            return existing, False

        review = SignalAIReview(
            candidate_id=candidate_id,
            status="PENDING",
            provider=provider,
            model=model,
            requested_direction=(
                requested_direction.upper()
            ),
            risk_flags=[],
        )
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review, True

    def mark_processing(
        self,
        review: SignalAIReview,
    ) -> SignalAIReview:
        if review.status != "PENDING":
            return review

        review.status = "PROCESSING"
        review.started_at = utc_now()
        self.db.commit()
        self.db.refresh(review)
        return review

    def complete(
        self,
        review: SignalAIReview,
        result: AIReviewResult,
    ) -> SignalAIReview:
        verdict = result.verdict

        review.status = (
            "APPROVED"
            if result.approved
            else "REJECTED"
        )
        review.result_reason = result.reason
        review.completed_at = utc_now()
        review.error_code = None

        if verdict is not None:
            review.verdict = verdict.verdict
            review.verdict_direction = (
                verdict.direction
            )
            review.ai_confidence = Decimal(
                str(verdict.confidence)
            )
            review.rationale = verdict.rationale
            review.risk_flags = list(
                verdict.risk_flags
            )

        self.db.commit()
        self.db.refresh(review)
        return review

    def fail(
        self,
        review: SignalAIReview,
        *,
        error_code: str,
    ) -> SignalAIReview:
        review.status = "FAILED"
        review.result_reason = (
            "AI_REVIEW_FAILED"
        )
        review.error_code = (
            error_code[:64].upper()
        )
        review.completed_at = utc_now()

        self.db.commit()
        self.db.refresh(review)
        return review
