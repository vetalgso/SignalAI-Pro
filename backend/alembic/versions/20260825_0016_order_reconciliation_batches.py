"""Add persisted order reconciliation batches.

Revision ID: 20260825_0016
Revises: 20260816_0015
Create Date: 2026-08-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260825_0016"
down_revision: str | None = "20260816_0015"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "order_reconciliation_batches",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),
        sa.Column(
            "action",
            sa.String(length=32),
            nullable=False,
            server_default="STARTED",
        ),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default="BINANCE_TESTNET",
        ),
        sa.Column(
            "read_only",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "scanned",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "reconciled",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "skipped",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "failed",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "errors",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        (
            "ix_order_reconciliation_batches_"
            "action_started_at"
        ),
        "order_reconciliation_batches",
        [
            "action",
            "started_at",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        (
            "ix_order_reconciliation_batches_"
            "action_started_at"
        ),
        table_name=(
            "order_reconciliation_batches"
        ),
    )

    op.drop_table(
        "order_reconciliation_batches"
    )
