from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExchangeAccount(Base):
    __tablename__ = "exchange_accounts"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "exchange",
            "environment",
            name=(
                "uq_exchange_accounts_"
                "user_exchange_environment"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    exchange: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="BINANCE",
    )

    environment: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="TESTNET",
    )

    label: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="Binance",
    )

    encrypted_api_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    encrypted_secret_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    api_key_hint: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="UNVERIFIED",
        index=True,
    )

    can_trade: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    can_deposit: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    can_withdraw: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    last_checked_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_error: Mapped[str | None] = mapped_column(
        String(255),
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
