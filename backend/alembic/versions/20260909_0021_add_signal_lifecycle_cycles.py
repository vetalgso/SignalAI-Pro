"""Persist signal lifecycle cycle diagnostics.

Revision ID: 20260909_0021
Revises: 20260903_0020
"""
from alembic import op
import sqlalchemy as sa

revision = "20260909_0021"
down_revision = "20260903_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_lifecycle_cycles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("worker_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("poll_interval_seconds", sa.Float(), nullable=False),
        sa.Column("checked_signals", sa.Integer(), nullable=True),
        sa.Column("updated_signals", sa.Integer(), nullable=True),
        sa.Column("transition_count", sa.Integer(), nullable=True),
        sa.Column("price_updates", sa.Integer(), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=True),
        sa.Column("error_counts", sa.JSON(), nullable=False),
    )
    op.create_index("ix_signal_lifecycle_cycles_started_at", "signal_lifecycle_cycles", ["started_at"])
    op.create_index("ix_signal_lifecycle_cycles_status", "signal_lifecycle_cycles", ["status"])


def downgrade() -> None:
    op.drop_index("ix_signal_lifecycle_cycles_status", table_name="signal_lifecycle_cycles")
    op.drop_index("ix_signal_lifecycle_cycles_started_at", table_name="signal_lifecycle_cycles")
    op.drop_table("signal_lifecycle_cycles")
