"""Add position price-source safety profile.

Revision ID: 20260803_0008
Revises: 20260803_0007
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260803_0008"
down_revision: Union[str, None] = (
    "20260803_0007"
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
    op.add_column(
        "trading_positions",
        sa.Column(
            "price_source",
            sa.String(length=32),
            nullable=False,
            server_default="MANUAL",
        ),
    )
    op.add_column(
        "trading_positions",
        sa.Column(
            "max_price_deviation_percent",
            sa.Numeric(10, 4),
            nullable=False,
            server_default="25",
        ),
    )

    op.create_index(
        "ix_trading_positions_price_source",
        "trading_positions",
        ["price_source"],
        unique=False,
    )

    op.alter_column(
        "trading_positions",
        "price_source",
        server_default=None,
    )
    op.alter_column(
        "trading_positions",
        "max_price_deviation_percent",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_trading_positions_price_source",
        table_name="trading_positions",
    )
    op.drop_column(
        "trading_positions",
        "max_price_deviation_percent",
    )
    op.drop_column(
        "trading_positions",
        "price_source",
    )
