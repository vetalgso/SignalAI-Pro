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
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SignalAIReview(Base):
    __tablename__ = "signal_ai_reviews"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            name=(
                "uq_signal_ai_reviews_candidate_id"
            ),
        ),
        Index(
            "ix_signal_ai_reviews_status_created",
            "status",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
    candidate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "signal_scan_candidates.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(
        String(96),
        nullable=False,
    )
    requested_direction: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    verdict: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )
    verdict_direction: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )
    ai_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    rationale: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    risk_flags: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    result_reason: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    def safe_summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "status": self.status,
            "provider": self.provider,
            "model": self.model,
            "requested_direction": (
                self.requested_direction
            ),
            "verdict": self.verdict,
            "verdict_direction": (
                self.verdict_direction
            ),
            "ai_confidence": (
                float(self.ai_confidence)
                if self.ai_confidence is not None
                else None
            ),
            "rationale": self.rationale,
            "risk_flags": list(
                self.risk_flags or []
            ),
            "result_reason": self.result_reason,
            "error_code": self.error_code,
        }
