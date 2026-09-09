"""Add portfolio snapshot history.

Revision ID: 20260803_0004
Revises: 20260801_0003
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260803_0004"
down_revision: Union[str, None] = (
    "20260801_0003"
)
branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None
depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_snapshots",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=24),
            nullable=False,
        ),
        sa.Column(
            "total_wallet_balance",
            sa.Numeric(
                precision=30,
                scale=12,
            ),
            nullable=True,
        ),
        sa.Column(
            "balances_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "open_orders_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "positions_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "snapshot_payload",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f(
            "ix_portfolio_snapshots_source"
        ),
        "portfolio_snapshots",
        ["source"],
        unique=False,
    )
    op.create_index(
        op.f(
            "ix_portfolio_snapshots_captured_at"
        ),
        "portfolio_snapshots",
        ["captured_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f(
            "ix_portfolio_snapshots_captured_at"
        ),
        table_name="portfolio_snapshots",
    )
    op.drop_index(
        op.f(
            "ix_portfolio_snapshots_source"
        ),
        table_name="portfolio_snapshots",
    )
    op.drop_table("portfolio_snapshots")
