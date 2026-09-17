from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SignalScanRun(Base):
    __tablename__ = "signal_scan_runs"
    __table_args__ = (
        Index(
            "ix_signal_scan_runs_created_at_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, index=True
    )
    universe_source: Mapped[str] = mapped_column(
        String(48), nullable=False, index=True
    )
    risk_level: Mapped[str] = mapped_column(
        String(16), nullable=False
    )
    minimum_confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    requested_limit: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    universe_assets: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    scanned_assets: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    successful_assets: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    failed_assets: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    opportunities_found: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    created_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    duplicate_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    skipped_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    rejection_reasons: Mapped[dict[str, int]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    scanner_errors: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class SignalScanCandidate(Base):
    __tablename__ = "signal_scan_candidates"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "symbol",
            name="uq_signal_scan_candidates_run_symbol",
        ),
        Index(
            "ix_signal_scan_candidates_symbol_created",
            "symbol",
            "created_at",
        ),
        Index(
            "ix_signal_scan_candidates_outcome_created",
            "outcome",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("signal_scan_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    asset: Mapped[str] = mapped_column(String(24), nullable=False)
    outcome: Mapped[str] = mapped_column(
        String(24), nullable=False, index=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    signal_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("trading_signals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recommendation: Mapped[str | None] = mapped_column(
        String(24), nullable=True
    )
    signal_action: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    trade_direction: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    risk_level: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    ranking_score: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True
    )
    snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
