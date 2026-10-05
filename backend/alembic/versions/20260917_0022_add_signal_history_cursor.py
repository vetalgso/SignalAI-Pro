"""Persist verified signal lifecycle progress without blessing legacy history.

Revision ID: 20260917_0022
Revises: 20260909_0021
"""
from alembic import op
import sqlalchemy as sa

revision = "20260917_0022"
down_revision = "20260909_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trading_signals", sa.Column(
        "lifecycle_next_candle_at", sa.DateTime(timezone=True), nullable=True,
    ))
    op.add_column("trading_signals", sa.Column(
        "lifecycle_history_status", sa.String(24), nullable=False,
        server_default="UNVERIFIED",
    ))


def downgrade() -> None:
    op.drop_column("trading_signals", "lifecycle_history_status")
    op.drop_column("trading_signals", "lifecycle_next_candle_at")
