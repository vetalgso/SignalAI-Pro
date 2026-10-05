"""Add TradingGPT order journal.

Revision ID: 20260801_0003
Revises: 20260724_0002
Create Date: 2026-08-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260801_0003"
down_revision: Union[str, None] = "20260724_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trading_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "idempotency_key",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "exchange",
            sa.String(length=24),
            nullable=False,
        ),
        sa.Column(
            "market_type",
            sa.String(length=24),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "side",
            sa.String(length=8),
            nullable=False,
        ),
        sa.Column(
            "order_type",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "requested_quantity",
            sa.Numeric(precision=30, scale=12),
            nullable=False,
        ),
        sa.Column(
            "normalized_quantity",
            sa.Numeric(precision=30, scale=12),
            nullable=True,
        ),
        sa.Column(
            "requested_price",
            sa.Numeric(precision=30, scale=12),
            nullable=True,
        ),
        sa.Column(
            "normalized_price",
            sa.Numeric(precision=30, scale=12),
            nullable=True,
        ),
        sa.Column(
            "filled_quantity",
            sa.Numeric(precision=30, scale=12),
            nullable=False,
        ),
        sa.Column(
            "average_price",
            sa.Numeric(precision=30, scale=12),
            nullable=True,
        ),
        sa.Column(
            "exchange_order_id",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column(
            "client_order_id",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column(
            "dry_run",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "simulated",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "request_payload",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "preview_payload",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "execution_payload",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "error_message",
            sa.Text(),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )

    op.create_index(
        op.f("ix_trading_orders_idempotency_key"),
        "trading_orders",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        op.f("ix_trading_orders_exchange"),
        "trading_orders",
        ["exchange"],
        unique=False,
    )
    op.create_index(
        op.f("ix_trading_orders_symbol"),
        "trading_orders",
        ["symbol"],
        unique=False,
    )
    op.create_index(
        op.f("ix_trading_orders_status"),
        "trading_orders",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_trading_orders_exchange_order_id"),
        "trading_orders",
        ["exchange_order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_trading_orders_client_order_id"),
        "trading_orders",
        ["client_order_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_trading_orders_client_order_id"),
        table_name="trading_orders",
    )
    op.drop_index(
        op.f("ix_trading_orders_exchange_order_id"),
        table_name="trading_orders",
    )
    op.drop_index(
        op.f("ix_trading_orders_status"),
        table_name="trading_orders",
    )
    op.drop_index(
        op.f("ix_trading_orders_symbol"),
        table_name="trading_orders",
    )
    op.drop_index(
        op.f("ix_trading_orders_exchange"),
        table_name="trading_orders",
    )
    op.drop_index(
        op.f("ix_trading_orders_idempotency_key"),
        table_name="trading_orders",
    )
    op.drop_table("trading_orders")
