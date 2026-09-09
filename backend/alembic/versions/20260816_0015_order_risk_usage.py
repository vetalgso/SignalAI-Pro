"""Add persisted order risk usage.

Revision ID: 20260816_0015
Revises: 20260806_0014
Create Date: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260816_0015"
down_revision: str | None = "20260806_0014"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trading_orders",
        sa.Column(
            "estimated_notional",
            sa.Numeric(
                precision=30,
                scale=12,
            ),
            nullable=True,
        ),
    )

    op.create_index(
        (
            "ix_trading_orders_"
            "account_risk_usage"
        ),
        "trading_orders",
        [
            "user_id",
            "exchange_account_id",
            "dry_run",
            "status",
            "created_at",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        (
            "ix_trading_orders_"
            "account_risk_usage"
        ),
        table_name="trading_orders",
    )

    op.drop_column(
        "trading_orders",
        "estimated_notional",
    )
