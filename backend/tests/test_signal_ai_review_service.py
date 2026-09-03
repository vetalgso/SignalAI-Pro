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


def candidate(db: Session) -> SignalScanCandidate:
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
        risk_level="HIGH",
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
    assert payload["confidence"] == 67
    assert payload["ranking_score"] == 70.22
    assert payload["signal_action"] == "LONG"
    assert payload["trade_direction"] == "LONG"
