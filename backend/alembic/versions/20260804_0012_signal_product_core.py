"""Add SignalAI product trading signals.

Revision ID: 20260804_0012
Revises: 20260803_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260804_0012"
down_revision: str | None = (
    "20260803_0011"
)
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trading_signals",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),
        sa.Column(
            "fingerprint",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "exchange",
            sa.String(length=24),
            nullable=False,
        ),
        sa.Column(
            "market_type",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "timeframe",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "side",
            sa.String(length=8),
            nullable=False,
        ),
        sa.Column(
            "strategy",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
        ),
        sa.Column(
            "confidence",
            sa.Numeric(5, 2),
            nullable=False,
        ),
        sa.Column(
            "risk_level",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "risk_reward",
            sa.Numeric(12, 4),
            nullable=False,
        ),
        sa.Column(
            "entry_min",
            sa.Numeric(30, 12),
            nullable=False,
        ),
        sa.Column(
            "entry_max",
            sa.Numeric(30, 12),
            nullable=False,
        ),
        sa.Column(
            "stop_loss",
            sa.Numeric(30, 12),
            nullable=False,
        ),
        sa.Column(
            "take_profit_1",
            sa.Numeric(30, 12),
            nullable=False,
        ),
        sa.Column(
            "take_profit_2",
            sa.Numeric(30, 12),
            nullable=True,
        ),
        sa.Column(
            "take_profit_3",
            sa.Numeric(30, 12),
            nullable=True,
        ),
        sa.Column(
            "current_price",
            sa.Numeric(30, 12),
            nullable=True,
        ),
        sa.Column(
            "reasons",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "metadata_payload",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "entry_reached_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "closed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "fingerprint",
            name=(
                "uq_trading_signals_"
                "fingerprint"
            ),
        ),
    )

    for column in (
        "fingerprint",
        "exchange",
        "symbol",
        "timeframe",
        "side",
        "strategy",
        "status",
        "risk_level",
        "source",
        "generated_at",
        "expires_at",
    ):
        op.create_index(
            f"ix_trading_signals_{column}",
            "trading_signals",
            [column],
        )

    op.create_table(
        "trading_signal_events",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),
        sa.Column(
            "signal_id",
            sa.Integer(),
            sa.ForeignKey(
                "trading_signals.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "from_status",
            sa.String(length=24),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            sa.String(length=24),
            nullable=False,
        ),
        sa.Column(
            "price",
            sa.Numeric(30, 12),
            nullable=True,
        ),
        sa.Column(
            "note",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "payload",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_trading_signal_events_signal_id",
        "trading_signal_events",
        ["signal_id"],
    )
    op.create_index(
        "ix_trading_signal_events_event_type",
        "trading_signal_events",
        ["event_type"],
    )
    op.create_index(
        "ix_trading_signal_events_created_at",
        "trading_signal_events",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_trading_signal_events_created_at",
        table_name="trading_signal_events",
    )
    op.drop_index(
        "ix_trading_signal_events_event_type",
        table_name="trading_signal_events",
    )
    op.drop_index(
        "ix_trading_signal_events_signal_id",
        table_name="trading_signal_events",
    )
    op.drop_table(
        "trading_signal_events"
    )

    for column in reversed(
        (
            "fingerprint",
            "exchange",
            "symbol",
            "timeframe",
            "side",
            "strategy",
            "status",
            "risk_level",
            "source",
            "generated_at",
            "expires_at",
        )
    ):
        op.drop_index(
            f"ix_trading_signals_{column}",
            table_name="trading_signals",
        )

    op.drop_table("trading_signals")
