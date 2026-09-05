from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    JSON,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class TradingPosition(Base):
    __tablename__ = "trading_positions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    journal_order_id: Mapped[int | None] = mapped_column(
        Integer,
        index=True,
        unique=True,
        nullable=True,
    )

    exchange: Mapped[str] = mapped_column(
        String(24),
        index=True,
        nullable=False,
    )
    market_type: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(
        String(32),
        index=True,
        nullable=False,
    )
    side: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        index=True,
        nullable=False,
        default="OPEN",
    )
    price_source: Mapped[str] = mapped_column(
        String(32),
        index=True,
        nullable=False,
        default="MANUAL",
    )
    max_price_deviation_percent: Mapped[
        Decimal
    ] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        default=Decimal("25"),
    )

    initial_quantity: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
        nullable=False,
    )
    remaining_quantity: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
        nullable=False,
    )
    closed_quantity: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
        nullable=False,
        default=Decimal("0"),
    )

    entry_price: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
        nullable=False,
    )
    current_price: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
        nullable=False,
    )
    exit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )

    stop_loss: Mapped[Decimal | None] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )
    take_profit_1: Mapped[Decimal | None] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )
    take_profit_2: Mapped[Decimal | None] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )

    tp1_close_percent: Mapped[Decimal] = mapped_column(
        Numeric(8, 4),
        nullable=False,
        default=Decimal("50"),
    )
    tp1_triggered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    tp2_triggered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    break_even_activated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    stop_loss_triggered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
        nullable=False,
        default=Decimal("0"),
    )
    unrealized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
        nullable=False,
        default=Decimal("0"),
    )

    metadata_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
