from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.signal_ai_review import SignalAIReview
from app.models.signal_discovery import SignalScanCandidate


router = APIRouter()

REASONS = frozenset({
    "AI_REVIEW_NOT_APPROVED", "PROMOTION_DIRECTION_CONFLICT",
    "PROMOTION_HIGH_RISK", "PROMOTION_TIMEFRAMES_UNAVAILABLE",
    "PROMOTION_TIMEFRAME_CONFLICT", "PROMOTION_BLOCKING_RISK",
    "PROMOTION_INTERNAL_ERROR", "PROMOTION_REQUEST_REJECTED",
    "PROMOTION_UNKNOWN_REASON",
})


class ReviewRow(BaseModel):
    id: int
    candidate_id: int
    run_id: int
    symbol: str
    status: Literal["PENDING", "PROCESSING", "APPROVED", "REJECTED", "FAILED", "UNKNOWN"]
    ai_confidence: float | None
    created_at: datetime
    promotion_action: Literal["CREATED", "DUPLICATE", "LINKED", "BLOCKED", "FAILED", "NOT_RECORDED"]
    promotion_reason: str | None
    signal_id: int | None


class ReviewPage(BaseModel):
    items: list[ReviewRow]
    total: int
    limit: int
    offset: int


def review_row(review: SignalAIReview, candidate: SignalScanCandidate) -> ReviewRow:
    snapshot = candidate.snapshot if isinstance(candidate.snapshot, dict) else {}
    success = snapshot.get("ai_promotion")
    attempt = snapshot.get("ai_promotion_attempt")
    action = "NOT_RECORDED"
    reason = None

    # A linked signal wins over a historical failed attempt. Never infer
    # CREATED versus DUPLICATE without a matching persisted record.
    if candidate.signal_id is not None:
        action = "LINKED"
        if (
            isinstance(success, dict)
            and success.get("review_id") == review.id
            and success.get("signal_id") == candidate.signal_id
            and success.get("action") in ("CREATED", "DUPLICATE")
        ):
            action = success["action"]
    elif (
        isinstance(attempt, dict)
        and attempt.get("review_id") == review.id
        and attempt.get("action") in ("BLOCKED", "FAILED")
    ):
        action = attempt["action"]
        raw_reason = attempt.get("reason")
        reason = raw_reason if isinstance(raw_reason, str) and raw_reason in REASONS else "PROMOTION_UNKNOWN_REASON"

    review_status = review.status
    if review_status not in ("PENDING", "PROCESSING", "APPROVED", "REJECTED", "FAILED"):
        review_status = "UNKNOWN"

    return ReviewRow(
        id=review.id, candidate_id=candidate.id, run_id=candidate.run_id,
        symbol=candidate.symbol, status=review_status,
        ai_confidence=review.ai_confidence, created_at=review.created_at,
        promotion_action=action, promotion_reason=reason,
        signal_id=candidate.signal_id,
    )


@router.get("/ai-reviews", response_model=ReviewPage)
def list_ai_reviews(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ReviewPage:
    joined = SignalAIReview.candidate_id == SignalScanCandidate.id
    total = db.scalar(select(func.count()).select_from(SignalAIReview).join(SignalScanCandidate, joined)) or 0
    rows = db.execute(
        select(SignalAIReview, SignalScanCandidate)
        .join(SignalScanCandidate, joined)
        .order_by(SignalAIReview.id.desc())
        .offset(offset).limit(limit)
    ).all()
    return ReviewPage(
        items=[review_row(review, candidate) for review, candidate in rows],
        total=total, limit=limit, offset=offset,
    )
