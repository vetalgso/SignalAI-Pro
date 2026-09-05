from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.base import Base
from app.models.signal_discovery import (
    SignalScanCandidate,
    SignalScanRun,
)
from app.tradinggpt.signals.ai_review_service import (
    SignalAIReviewService,
)
from app.tradinggpt.signals.ai_reviewer import (
    AIReviewError,
    AIReviewResult,
    AIReviewVerdict,
)


class ApprovingReviewer:
    def __init__(self) -> None:
        self.calls = 0

    async def review(self, candidate):
        self.calls += 1
        assert candidate["symbol"] == "BNBUSDT"
        assert candidate["rejection_reason"] == (
            "RECOMMENDATION_CONFLICT"
        )

        return AIReviewResult(
            eligible=True,
            approved=True,
            reason="AI_APPROVED",
            verdict=AIReviewVerdict(
                verdict="APPROVE",
                direction="LONG",
                confidence=76,
                rationale="Evidence aligned.",
                risk_flags=[],
            ),
        )


class FailingReviewer:
    async def review(self, candidate):
        raise AIReviewError(
            "AI Review request failed"
        )


def settings():
    return Settings(
        _env_file=None,
        signal_ai_review_enabled=True,
        signal_ai_api_key="sk-test-placeholder",
    )


def session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def candidate(
    db: Session,
    *,
    risk_level: str = "HIGH",
) -> SignalScanCandidate:
    now = datetime.now(timezone.utc)
    run = SignalScanRun(
        status="COMPLETED",
        universe_source="TEST",
        risk_level="MEDIUM",
        minimum_confidence=60,
        requested_limit=1,
        universe_assets=["BNB"],
        scanned_assets=1,
        successful_assets=1,
        failed_assets=0,
        opportunities_found=0,
        created_count=0,
        duplicate_count=0,
        skipped_count=1,
        rejection_reasons={
            "RECOMMENDATION_CONFLICT": 1
        },
        scanner_errors=[],
        started_at=now,
        completed_at=now,
    )
    db.add(run)
    db.flush()

    item = SignalScanCandidate(
        run_id=run.id,
        symbol="BNBUSDT",
        asset="BNB",
        outcome="REJECTED",
        rejection_reason=(
            "RECOMMENDATION_CONFLICT"
        ),
        recommendation="WAIT",
        signal_action="LONG",
        trade_direction="LONG",
        confidence=67,
        risk_level=risk_level,
        ranking_score=70.22,
        snapshot={
            "score": 78.17,
            "opportunity_score": 47.04,
            "consensus_score": 100,
            "timeframe_consensus_score": 100,
            "quality_penalty": 5,
            "signal_levels": {
                "entry": "714.24",
                "stop_loss": "707.98",
                "take_profit": "726.74",
            },
        },
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_candidate_is_reviewed_once() -> None:
    db = session()
    item = candidate(db)
    reviewer = ApprovingReviewer()
    service = SignalAIReviewService(
        db=db,
        settings=settings(),
        reviewer=reviewer,
    )

    first = service.review_candidate(item.id)
    second = service.review_candidate(item.id)

    assert first["action"] == "APPROVED"
    assert (
        second["action"]
        == "ALREADY_REVIEWED"
    )
    assert reviewer.calls == 1
    assert first["review"]["candidate_id"] == item.id


def test_missing_candidate_is_not_reviewed() -> None:
    db = session()
    reviewer = ApprovingReviewer()
    service = SignalAIReviewService(
        db=db,
        settings=settings(),
        reviewer=reviewer,
    )

    result = service.review_candidate(999)

    assert result == {
        "action": "NOT_FOUND",
        "candidate_id": 999,
    }
    assert reviewer.calls == 0


def test_provider_failure_is_persisted() -> None:
    db = session()
    item = candidate(db)
    service = SignalAIReviewService(
        db=db,
        settings=settings(),
        reviewer=FailingReviewer(),
    )

    result = service.review_candidate(item.id)

    assert result["action"] == "FAILED"
    assert (
        result["review"]["error_code"]
        == "PROVIDER_ERROR"
    )
    assert "sk-" not in str(result)


def test_candidate_snapshot_is_normalized() -> None:
    db = session()
    item = candidate(db)

    payload = (
        SignalAIReviewService
        ._candidate_payload(item)
    )

    assert payload["candidate_id"] == item.id
    assert 0 <= payload[
        "candidate_age_seconds"
    ] < 10
    assert payload["confidence"] == 67
    assert payload["ranking_score"] == 70.22
    assert payload["signal_action"] == "LONG"
    assert payload["trade_direction"] == "LONG"

def test_scan_run_reviews_eligible_candidates() -> None:
    db = session()
    item = candidate(
        db,
        risk_level="MEDIUM",
    )
    reviewer = ApprovingReviewer()
    service = SignalAIReviewService(
        db=db,
        settings=settings(),
        reviewer=reviewer,
    )

    result = service.review_scan_run(
        item.run_id
    )

    assert result["action"] == "COMPLETED"
    assert result["eligible_candidates"] == 1
    assert result["promotion_risk_skips"] == 0
    assert result["selected_candidates"] == 1
    assert result["approved_count"] == 1
    assert result["rejected_count"] == 0
    assert result["failed_count"] == 0
    assert reviewer.calls == 1


def test_scan_run_skips_stale_candidate() -> None:
    from datetime import timedelta

    db = session()
    item = candidate(
        db,
        risk_level="MEDIUM",
    )
    item.created_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=10)
    )
    db.commit()

    reviewer = ApprovingReviewer()
    service = SignalAIReviewService(
        db=db,
        settings=settings(),
        reviewer=reviewer,
    )

    result = service.review_scan_run(
        item.run_id
    )

    assert result["eligible_candidates"] == 0
    assert result["selected_candidates"] == 0
    assert result["approved_count"] == 0
    assert reviewer.calls == 0

def test_scan_run_does_not_spend_ai_slot_on_high_risk() -> None:
    db = session()
    item = candidate(
        db,
        risk_level="HIGH",
    )
    reviewer = ApprovingReviewer()
    service = SignalAIReviewService(
        db=db,
        settings=settings(),
        reviewer=reviewer,
    )

    result = service.review_scan_run(
        item.run_id
    )

    assert result["action"] == "COMPLETED"
    assert result["eligible_candidates"] == 0
    assert result["promotion_risk_skips"] == 1
    assert result["selected_candidates"] == 0
    assert result["approved_count"] == 0
    assert result["rejected_count"] == 0
    assert result["failed_count"] == 0
    assert result["results"] == []
    assert reviewer.calls == 0


class RecordingPromoter:
    def __init__(self) -> None:
        self.calls = []

    def promote(
        self,
        *,
        candidate,
        review,
    ):
        self.calls.append(
            {
                "candidate_id": candidate.id,
                "review_id": review.id,
            }
        )

        return {
            "action": "CREATED",
            "candidate_id": candidate.id,
            "review_id": review.id,
            "signal_id": 901,
        }


def test_approved_review_runs_configured_promoter() -> None:
    db = session()
    item = candidate(db)
    promoter = RecordingPromoter()

    service = SignalAIReviewService(
        db=db,
        settings=settings(),
        reviewer=ApprovingReviewer(),
        promoter=promoter,
    )

    result = service.review_candidate(item.id)

    assert result["action"] == "APPROVED"
    assert result["promotion"]["action"] == "CREATED"
    assert result["promotion"]["signal_id"] == 901
    assert promoter.calls == [
        {
            "candidate_id": item.id,
            "review_id": result["review"]["id"],
        }
    ]


def test_rejected_review_does_not_run_promoter() -> None:
    db = session()
    item = candidate(db)
    promoter = RecordingPromoter()

    class RejectingReviewer:
        async def review(self, candidate_payload):
            return AIReviewResult(
                eligible=True,
                approved=False,
                reason="AI_REJECTED",
                verdict=AIReviewVerdict(
                    verdict="REJECT",
                    direction="LONG",
                    confidence=70,
                    rationale="Risk is excessive.",
                    risk_flags=[],
                ),
            )

    service = SignalAIReviewService(
        db=db,
        settings=settings(),
        reviewer=RejectingReviewer(),
        promoter=promoter,
    )

    result = service.review_candidate(item.id)

    assert result["action"] == "REJECTED"
    assert result["promotion"] == {
        "action": "SKIPPED_NOT_APPROVED",
        "candidate_id": item.id,
    }
    assert promoter.calls == []


def test_scan_run_does_not_spend_ai_slot_on_tight_geometry(
) -> None:
    db = session()
    item = candidate(
        db,
        risk_level="MEDIUM",
    )

    snapshot = dict(item.snapshot)
    snapshot["signal_levels"] = {
        "entry": "100",
        "stop_loss": "99.80",
        "take_profit": "101",
    }
    item.snapshot = snapshot
    db.commit()

    reviewer = ApprovingReviewer()
    service = SignalAIReviewService(
        db=db,
        settings=settings(),
        reviewer=reviewer,
    )

    result = service.review_scan_run(
        item.run_id
    )

    assert result["action"] == "COMPLETED"
    assert result["eligible_candidates"] == 0
    assert result["selected_candidates"] == 0
    assert result["approved_count"] == 0
    assert result["rejected_count"] == 0
    assert result["failed_count"] == 0
    assert result["results"] == []
    assert reviewer.calls == 0
