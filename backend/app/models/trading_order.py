from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class TradingOrder(Base):
    __tablename__ = "trading_orders"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name=(
                "uq_trading_orders_"
                "user_id_idempotency_key"
            ),
        ),
        Index(
            "uq_trading_orders_"
            "system_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text(
                "user_id IS NULL"
            ),
            sqlite_where=text(
                "user_id IS NULL"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    exchange_account_id: Mapped[
        int | None
    ] = mapped_column(
        ForeignKey(
            "exchange_accounts.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        index=True,
        nullable=False,
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
    order_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        index=True,
        nullable=False,
        default="PENDING",
    )

    requested_quantity: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
        nullable=False,
    )
    normalized_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )

    requested_price: Mapped[Decimal | None] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )
    normalized_price: Mapped[Decimal | None] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )

    filled_quantity: Mapped[Decimal] = mapped_column(
        Numeric(30, 12),
        nullable=False,
        default=Decimal("0"),
    )
    average_price: Mapped[Decimal | None] = mapped_column(
        Numeric(30, 12),
        nullable=True,
    )

    exchange_order_id: Mapped[str | None] = mapped_column(
        String(128),
        index=True,
        nullable=True,
    )
    client_order_id: Mapped[str | None] = mapped_column(
        String(128),
        index=True,
        nullable=True,
    )

    dry_run: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    simulated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    request_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    preview_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    execution_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
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
