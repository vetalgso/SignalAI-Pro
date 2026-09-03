from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.signal_discovery import (
    SignalScanCandidate,
    SignalScanRun,
)
from app.tradinggpt.signals.discovery_repository import (
    SignalDiscoveryRepository,
)


NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)


def test_records_complete_candidate_funnel() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        run = SignalDiscoveryRepository(db).record_completed_scan(
            scan_result={
                "universe_source": "BINANCE_24H_QUOTE_VOLUME",
                "universe_assets": ["BTC", "ETH", "SOL"],
                "scanned_assets": 3,
                "successful_assets": 2,
                "failed_assets": 1,
                "candidates": [
                    {
                        "asset": "BTC",
                        "symbol": "BTCUSDT",
                        "recommendation": "LONG",
                        "signal_action": "LONG",
                        "trade_direction": "LONG",
                        "confidence": 78,
                        "risk": "medium",
                        "ranking_score": 81.5,
                    },
                    {
                        "asset": "ETH",
                        "symbol": "ETHUSDT",
                        "recommendation": "WAIT",
                        "signal_action": None,
                        "trade_direction": "LONG",
                        "confidence": 55,
                        "risk": "low",
                        "ranking_score": 62,
                    },
                ],
                "errors": [
                    {"asset": "SOL", "error": "TimeoutError"}
                ],
            },
            persistence_result={
                "opportunities_found": 1,
                "created_count": 1,
                "duplicate_count": 0,
                "skipped_count": 1,
                "rejection_reasons": {
                    "NO_ACTIONABLE_TECHNICAL_SIGNAL": 1
                },
                "evaluations": [
                    {
                        "symbol": "BTCUSDT",
                        "outcome": "CREATED",
                        "signal_id": None,
                    },
                    {
                        "symbol": "ETHUSDT",
                        "outcome": "REJECTED",
                        "reason": "NO_ACTIONABLE_TECHNICAL_SIGNAL",
                    },
                ],
            },
            risk_level="medium",
            minimum_confidence=Decimal("60"),
            requested_limit=3,
            started_at=NOW,
            completed_at=NOW,
        )

        candidates = list(
            db.scalars(
                select(SignalScanCandidate).order_by(
                    SignalScanCandidate.symbol
                )
            ).all()
        )

        assert run.id is not None
        assert run.scanned_assets == 3
        assert run.created_count == 1
        assert run.rejection_reasons == {
            "NO_ACTIONABLE_TECHNICAL_SIGNAL": 1
        }
        assert [item.symbol for item in candidates] == [
            "BTCUSDT",
            "ETHUSDT",
            "SOLUSDT",
        ]
        outcomes = {item.symbol: item.outcome for item in candidates}
        assert outcomes == {
            "BTCUSDT": "CREATED",
            "ETHUSDT": "REJECTED",
            "SOLUSDT": "ANALYSIS_FAILED",
        }


def test_records_active_signal_suppression() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        run = SignalDiscoveryRepository(db).record_completed_scan(
            scan_result={
                "universe_source": "TEST",
                "universe_assets": ["BTC"],
                "scanned_assets": 1,
                "successful_assets": 1,
                "failed_assets": 0,
                "candidates": [
                    {
                        "asset": "BTC",
                        "symbol": "BTCUSDT",
                        "confidence": 80,
                    }
                ],
                "errors": [],
            },
            persistence_result={
                "opportunities_found": 1,
                "created_count": 0,
                "duplicate_count": 0,
                "skipped_count": 0,
                "rejection_reasons": {},
                "evaluations": [],
            },
            risk_level="medium",
            minimum_confidence=Decimal("60"),
            requested_limit=1,
            started_at=NOW,
            completed_at=NOW,
            suppressed_symbols={"BTCUSDT"},
        )

        candidate = db.scalar(select(SignalScanCandidate))
        assert candidate is not None
        assert candidate.outcome == "REJECTED"
        assert candidate.rejection_reason == "ACTIVE_SIGNAL"
        assert run.rejection_reasons == {"ACTIVE_SIGNAL": 1}
        assert run.skipped_count == 1


def test_discovery_migration_contract() -> None:
    migration = Path(
        "alembic/versions/"
        "20260903_0019_add_signal_discovery_journal.py"
    ).read_text(encoding="utf-8")

    for value in (
        'revision = "20260903_0019"',
        'down_revision = "20260828_0018"',
        '"signal_scan_runs"',
        '"signal_scan_candidates"',
        '"rejection_reasons"',
        '"snapshot"',
        '"uq_signal_scan_candidates_run_symbol"',
    ):
        assert value in migration
