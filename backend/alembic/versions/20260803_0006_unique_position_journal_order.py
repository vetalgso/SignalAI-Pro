"""Make position journal link unique.

Revision ID: 20260803_0006
Revises: 20260803_0005
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260803_0006"
down_revision: Union[str, None] = (
    "20260803_0005"
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
    op.drop_index(
        "ix_trading_positions_journal_order_id",
        table_name="trading_positions",
    )

    op.create_index(
        "ix_trading_positions_journal_order_id",
        "trading_positions",
        ["journal_order_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_trading_positions_journal_order_id",
        table_name="trading_positions",
    )

    op.create_index(
        "ix_trading_positions_journal_order_id",
        "trading_positions",
        ["journal_order_id"],
        unique=False,
    )
