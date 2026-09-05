"""Add persistent Signal AI Review journal.

Revision ID: 20260903_0020
Revises: 20260903_0019
"""

from alembic import op
import sqlalchemy as sa


revision = "20260903_0020"
down_revision = "20260903_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_ai_reviews",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "model",
            sa.String(length=96),
            nullable=False,
        ),
        sa.Column(
            "requested_direction",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "verdict",
            sa.String(length=16),
            nullable=True,
        ),
        sa.Column(
            "verdict_direction",
            sa.String(length=16),
            nullable=True,
        ),
        sa.Column(
            "ai_confidence",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
        ),
        sa.Column(
            "rationale",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "risk_flags",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "result_reason",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "error_code",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
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
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["signal_scan_candidates.id"],
            name=(
                "fk_signal_ai_reviews_candidate_id"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="signal_ai_reviews_pkey",
        ),
        sa.UniqueConstraint(
            "candidate_id",
            name=(
                "uq_signal_ai_reviews_candidate_id"
            ),
        ),
    )
    op.create_index(
        "ix_signal_ai_reviews_candidate_id",
        "signal_ai_reviews",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        "ix_signal_ai_reviews_status",
        "signal_ai_reviews",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_signal_ai_reviews_status_created",
        "signal_ai_reviews",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_signal_ai_reviews_status_created",
        table_name="signal_ai_reviews",
    )
    op.drop_index(
        "ix_signal_ai_reviews_status",
        table_name="signal_ai_reviews",
    )
    op.drop_index(
        "ix_signal_ai_reviews_candidate_id",
        table_name="signal_ai_reviews",
    )
    op.drop_table("signal_ai_reviews")
