from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class OrderReconciliationBatch(Base):
    __tablename__ = (
        "order_reconciliation_batches"
    )
    __table_args__ = (
        Index(
            (
                "ix_order_reconciliation_batches_"
                "action_started_at"
            ),
            "action",
            "started_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
    action: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="STARTED",
    )
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="BINANCE_TESTNET",
    )
    read_only: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    scanned: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    reconciled: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    skipped: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    errors: Mapped[
        list[str] | None
    ] = mapped_column(
        JSON,
        nullable=True,
    )
    error_message: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
    )
    finished_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
