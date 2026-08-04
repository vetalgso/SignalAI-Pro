from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TradingSignal(Base):
    __tablename__ = "trading_signals"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    exchange: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        index=True,
    )
    market_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="SPOT",
    )
    symbol: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        index=True,
    )
    side: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        index=True,
    )
    strategy: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="ACTIVE",
        index=True,
    )

    confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )
    risk_level: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        index=True,
    )
    risk_reward: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    entry_min: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
        nullable=False,
    )
    entry_max: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
        nullable=False,
    )
    stop_loss: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
        nullable=False,
    )
    take_profit_1: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
        nullable=False,
    )
    take_profit_2: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )
    take_profit_3: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )
    current_price: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )

    reasons: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    metadata_payload: Mapped[
        dict[str, Any]
    ] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="SCANNER",
        index=True,
    )

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )
    expires_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    activated_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    entry_reached_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    closed_at: Mapped[
        datetime | None
    ] = mapped_column(
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


class TradingSignalEvent(Base):
    __tablename__ = "trading_signal_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
    signal_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "trading_signals.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    from_status: Mapped[
        str | None
    ] = mapped_column(
        String(24),
        nullable=True,
    )
    to_status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
    )
    price: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    payload: Mapped[
        dict[str, Any]
    ] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )
