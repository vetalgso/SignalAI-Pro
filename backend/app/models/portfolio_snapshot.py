from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    Integer,
    JSON,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PortfolioSnapshotRecord(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
    source: Mapped[str] = mapped_column(
        String(24),
        index=True,
        nullable=False,
    )
    total_wallet_balance: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )
    balances_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    open_orders_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    positions_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    snapshot_payload: Mapped[
        dict[str, Any]
    ] = mapped_column(
        JSON,
        nullable=False,
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
