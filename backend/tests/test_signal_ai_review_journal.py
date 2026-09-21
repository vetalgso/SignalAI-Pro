from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.signal_ai_review import SignalAIReview
from app.models.signal_discovery import (
    SignalScanCandidate,
    SignalScanRun,
)
from app.tradinggpt.signals.ai_review_repository import (
    SignalAIReviewRepository,
)
from app.tradinggpt.signals.ai_reviewer import (
    AIReviewResult,
    AIReviewVerdict,
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
        snapshot={},
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_ai_review_is_idempotent_per_candidate() -> None:
    db = session()
    item = candidate(db)
    repository = SignalAIReviewRepository(db)

    first, created = repository.create_pending(
        candidate_id=item.id,
        provider="openai",
        model="gpt-5-mini",
        requested_direction="LONG",
    )
    second, created_again = (
        repository.create_pending(
            candidate_id=item.id,
            provider="openai",
            model="gpt-5-mini",
            requested_direction="LONG",
        )
    )

    assert created is True
    assert created_again is False
    assert first.id == second.id


def test_ai_review_approval_is_persisted() -> None:
    db = session()
    item = candidate(db)
    repository = SignalAIReviewRepository(db)

    review, _ = repository.create_pending(
        candidate_id=item.id,
        provider="openai",
        model="gpt-5-mini",
        requested_direction="LONG",
    )
    repository.mark_processing(review)

    completed = repository.complete(
        review,
        AIReviewResult(
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
        ),
    )

    assert completed.status == "APPROVED"
    assert completed.verdict == "APPROVE"
    assert completed.verdict_direction == "LONG"
    assert float(completed.ai_confidence) == 76
    assert completed.result_reason == "AI_APPROVED"


def test_ai_review_failure_is_sanitized() -> None:
    db = session()
    item = candidate(db)
    repository = SignalAIReviewRepository(db)

    review, _ = repository.create_pending(
        candidate_id=item.id,
        provider="openai",
        model="gpt-5-mini",
        requested_direction="LONG",
    )
    failed = repository.fail(
        review,
        error_code="provider_timeout",
    )

    assert failed.status == "FAILED"
    assert failed.error_code == "PROVIDER_TIMEOUT"
    assert "sk-" not in str(failed.safe_summary())


def test_ai_review_migration_contract() -> None:
    migration = Path(
        "alembic/versions/"
        "20260903_0020_add_signal_ai_review_journal.py"
    ).read_text(encoding="utf-8")

    for value in (
        'revision = "20260903_0020"',
        'down_revision = "20260903_0019"',
        '"signal_ai_reviews"',
        '"candidate_id"',
        '"requested_direction"',
        '"verdict_direction"',
        '"ai_confidence"',
        "uq_signal_ai_reviews_candidate_id",
        "fk_signal_ai_reviews_candidate_id",
    ):
        assert value in migration


def test_ai_review_model_is_registered() -> None:
    assert (
        "signal_ai_reviews"
        in Base.metadata.tables
    )
    assert SignalAIReview.__tablename__ == (
        "signal_ai_reviews"
    )


def test_review_projection_preserves_success_over_old_failure() -> None:
    from app.tradinggpt.signals.ai_review_read import review_row

    db = session()
    item = candidate(db)
    review, _ = SignalAIReviewRepository(db).create_pending(
        candidate_id=item.id, provider="openai", model="test", requested_direction="LONG",
    )
    item.signal_id = 42
    item.snapshot = {
        "ai_promotion": {"action": "DUPLICATE", "review_id": review.id, "signal_id": 42},
        "ai_promotion_attempt": {"action": "FAILED", "reason": "PROMOTION_INTERNAL_ERROR", "review_id": review.id},
    }
    row = review_row(review, item)
    assert row.promotion_action == "DUPLICATE"
    assert row.promotion_reason is None
    assert row.signal_id == 42
    item.snapshot = {}
    assert review_row(review, item).promotion_action == "LINKED"
    db.close()


def test_review_projection_missing_malformed_and_private_diagnostics() -> None:
    from app.tradinggpt.signals.ai_review_read import review_row

    db = session()
    item = candidate(db)
    review, _ = SignalAIReviewRepository(db).create_pending(
        candidate_id=item.id, provider="openai", model="test", requested_direction="LONG",
    )
    for snapshot in (None, [], {}, {"ai_promotion_attempt": "private payload"}):
        item.snapshot = snapshot
        assert review_row(review, item).promotion_action == "NOT_RECORDED"
    item.snapshot = {"ai_promotion_attempt": {
        "action": "BLOCKED", "reason": "PROMOTION_HIGH_RISK", "review_id": review.id,
    }}
    assert review_row(review, item).promotion_reason == "PROMOTION_HIGH_RISK"
    item.snapshot = {"ai_promotion_attempt": {
        "action": "FAILED", "reason": "private exception message", "review_id": review.id,
    }, "credentials": "private credential"}
    row = review_row(review, item)
    assert row.promotion_reason == "PROMOTION_UNKNOWN_REASON"
    assert "private" not in row.model_dump_json()
    item.snapshot = {"ai_promotion_attempt": {
        "action": "FAILED", "reason": "PROMOTION_INTERNAL_ERROR", "review_id": review.id + 1,
    }}
    assert review_row(review, item).promotion_action == "NOT_RECORDED"
    db.close()


def test_review_endpoint_pagination_and_validation() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool
    from app.database.session import get_db
    from app.tradinggpt.signals.router import router

    engine = create_engine("sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = Session(engine)
    review_ids = []
    for _ in range(2):
        item = candidate(db)
        review, _ = SignalAIReviewRepository(db).create_pending(
            candidate_id=item.id, provider="openai", model="test", requested_direction="LONG",
        )
        review_ids.append(review.id)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        response = client.get("/signals/ai-reviews?limit=1")
        assert response.status_code == 200
        assert response.json()["total"] == 2
        assert response.json()["items"][0]["id"] == review_ids[1]
        assert response.json()["items"][0]["promotion_action"] == "NOT_RECORDED"
        assert client.get("/signals/ai-reviews?limit=1&offset=1").json()["items"][0]["id"] == review_ids[0]
        assert client.get("/signals/ai-reviews?offset=2").json()["items"] == []
        assert client.get("/signals/ai-reviews?limit=101").status_code == 422
        assert client.get("/signals/ai-reviews?offset=-1").status_code == 422
    assert db.query(SignalAIReview).count() == 2
    db.close()
    engine.dispose()


def admission_record(**overrides):
    return {
        "version": 1, "action": "SKIPPED", "reason": "LOW_CONFIDENCE",
        "confidence": 42, "minimum_confidence": 65, "candidate_age_seconds": 2,
        "max_candidates": 1, "evaluated_at": "2026-09-19T06:20:00Z", **overrides,
    }


def test_admission_projection_ignores_legacy_malformed_and_private_data():
    from app.tradinggpt.signals.ai_admission import read_admission

    for snapshot in (None, [], {}, {"ai_admission": "private"}):
        assert read_admission(snapshot) is None
    for record in (
        admission_record(reason="private"), admission_record(version=999),
        admission_record(action="SELECTED"), admission_record(confidence=float("nan")),
        admission_record(evaluated_at="not a date"),
    ):
        assert read_admission({"ai_admission": record}) is None
    result = read_admission({"ai_admission": admission_record(secret="private"), "key": "private"})
    assert result.minimum_confidence == 65
    assert "private" not in result.model_dump_json()


def test_admission_endpoint_pins_scan_and_counts_unrecorded_across_pages():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool
    from app.database.session import get_db
    from app.tradinggpt.signals.router import router

    engine = create_engine("sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            assert client.get("/signals/ai-admission").json()["run"] is None
            first = candidate(db)
            run_id = first.run_id
            first.snapshot = {"ai_admission": admission_record(), "secret": "private"}
            legacy = SignalScanCandidate(
                run_id=run_id, symbol="BTCUSDT", asset="BTC", outcome="REJECTED",
                rejection_reason="RECOMMENDATION_CONFLICT", snapshot={},
            )
            unrelated = SignalScanCandidate(
                run_id=run_id, symbol="ETHUSDT", asset="ETH", outcome="REJECTED",
                rejection_reason="NO_ACTIONABLE_TECHNICAL_SIGNAL", snapshot={},
            )
            db.add_all([legacy, unrelated])
            db.commit()
            response = client.get("/signals/ai-admission?limit=1")
            page = response.json()
            assert response.status_code == 200
            assert page["run"]["id"] == run_id
            assert page["total"] == 2
            assert page["reason_counts"] == {"LOW_CONFIDENCE": 1}
            assert page["not_recorded_count"] == 1
            assert page["items"][0]["decision"]["minimum_confidence"] == 65
            assert "private" not in response.text
            newer = candidate(db)
            assert client.get("/signals/ai-admission").json()["run"]["id"] == newer.run_id
            old = client.get(f"/signals/ai-admission?run_id={run_id}&limit=1&offset=1").json()
            assert old["run"]["id"] == run_id
            assert old["items"][0]["decision"] is None
            assert old["reason_counts"] == page["reason_counts"]
            assert client.get(f"/signals/ai-admission?run_id={run_id}&offset=2").json()["items"] == []
            assert client.get("/signals/ai-admission?run_id=99999").status_code == 404
            for query in ("limit=101", "offset=-1", "run_id=0"):
                assert client.get(f"/signals/ai-admission?{query}").status_code == 422
            assert db.query(SignalAIReview).count() == 0
            assert legacy.snapshot == {}
    engine.dispose()
