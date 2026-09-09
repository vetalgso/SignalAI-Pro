"""Add persistent signal discovery journal.

Revision ID: 20260903_0019
Revises: 20260828_0018
"""

from alembic import op
import sqlalchemy as sa


revision = "20260903_0019"
down_revision = "20260828_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_scan_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("universe_source", sa.String(length=48), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("minimum_confidence", sa.Numeric(5, 2), nullable=False),
        sa.Column("requested_limit", sa.Integer(), nullable=False),
        sa.Column("universe_assets", sa.JSON(), nullable=False),
        sa.Column("scanned_assets", sa.Integer(), nullable=False),
        sa.Column("successful_assets", sa.Integer(), nullable=False),
        sa.Column("failed_assets", sa.Integer(), nullable=False),
        sa.Column("opportunities_found", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("rejection_reasons", sa.JSON(), nullable=False),
        sa.Column("scanner_errors", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_signal_scan_runs_status",
        "signal_scan_runs",
        ["status"],
    )
    op.create_index(
        "ix_signal_scan_runs_universe_source",
        "signal_scan_runs",
        ["universe_source"],
    )
    op.create_index(
        "ix_signal_scan_runs_created_at_id",
        "signal_scan_runs",
        ["created_at", "id"],
    )

    op.create_table(
        "signal_scan_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("signal_scan_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("asset", sa.String(length=24), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("rejection_reason", sa.String(length=64), nullable=True),
        sa.Column(
            "signal_id",
            sa.Integer(),
            sa.ForeignKey("trading_signals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("recommendation", sa.String(length=24), nullable=True),
        sa.Column("signal_action", sa.String(length=16), nullable=True),
        sa.Column("trade_direction", sa.String(length=16), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("risk_level", sa.String(length=16), nullable=True),
        sa.Column("ranking_score", sa.Numeric(8, 2), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "run_id",
            "symbol",
            name="uq_signal_scan_candidates_run_symbol",
        ),
    )
    for column in (
        "run_id",
        "symbol",
        "outcome",
        "rejection_reason",
        "signal_id",
    ):
        op.create_index(
            f"ix_signal_scan_candidates_{column}",
            "signal_scan_candidates",
            [column],
        )
    op.create_index(
        "ix_signal_scan_candidates_symbol_created",
        "signal_scan_candidates",
        ["symbol", "created_at"],
    )
    op.create_index(
        "ix_signal_scan_candidates_outcome_created",
        "signal_scan_candidates",
        ["outcome", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("signal_scan_candidates")
    op.drop_table("signal_scan_runs")
