"""Add managed trading positions.

Revision ID: 20260803_0005
Revises: 20260803_0004
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260803_0005"
down_revision: Union[str, None] = (
    "20260803_0004"
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
        "trading_positions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "journal_order_id",
            sa.Integer(),
            nullable=True,
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
            "status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "initial_quantity",
            sa.Numeric(30, 12),
            nullable=False,
        ),
        sa.Column(
            "remaining_quantity",
            sa.Numeric(30, 12),
            nullable=False,
        ),
        sa.Column(
            "closed_quantity",
            sa.Numeric(30, 12),
            nullable=False,
        ),
        sa.Column(
            "entry_price",
            sa.Numeric(30, 12),
            nullable=False,
        ),
        sa.Column(
            "current_price",
            sa.Numeric(30, 12),
            nullable=False,
        ),
        sa.Column(
            "exit_price",
            sa.Numeric(30, 12),
            nullable=True,
        ),
        sa.Column(
            "stop_loss",
            sa.Numeric(30, 12),
            nullable=True,
        ),
        sa.Column(
            "take_profit_1",
            sa.Numeric(30, 12),
            nullable=True,
        ),
        sa.Column(
            "take_profit_2",
            sa.Numeric(30, 12),
            nullable=True,
        ),
        sa.Column(
            "tp1_close_percent",
            sa.Numeric(8, 4),
            nullable=False,
        ),
        sa.Column(
            "tp1_triggered",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "tp2_triggered",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "break_even_activated",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "stop_loss_triggered",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "realized_pnl",
            sa.Numeric(30, 12),
            nullable=False,
        ),
        sa.Column(
            "unrealized_pnl",
            sa.Numeric(30, 12),
            nullable=False,
        ),
        sa.Column(
            "metadata_payload",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "closed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    for column in (
        "journal_order_id",
        "exchange",
        "symbol",
        "status",
    ):
        op.create_index(
            op.f(
                f"ix_trading_positions_{column}"
            ),
            "trading_positions",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in (
        "status",
        "symbol",
        "exchange",
        "journal_order_id",
    ):
        op.drop_index(
            op.f(
                f"ix_trading_positions_{column}"
            ),
            table_name="trading_positions",
        )

    op.drop_table("trading_positions")
