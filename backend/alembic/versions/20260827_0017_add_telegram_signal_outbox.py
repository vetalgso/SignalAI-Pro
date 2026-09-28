"""Add Telegram signal delivery outbox.

Revision ID: 20260827_0017
Revises: 20260825_0016
"""

from alembic import op
import sqlalchemy as sa


revision = "20260827_0017"
down_revision = "20260825_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_signal_deliveries",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),
        sa.Column(
            "signal_id",
            sa.Integer(),
            sa.ForeignKey(
                "trading_signals.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "locked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "telegram_message_id",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "signal_id",
            name=(
                "uq_telegram_signal_"
                "deliveries_signal_id"
            ),
        ),
    )

    op.create_index(
        (
            "ix_telegram_signal_deliveries_"
            "status_next_attempt"
        ),
        "telegram_signal_deliveries",
        [
            "status",
            "next_attempt_at",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        (
            "ix_telegram_signal_deliveries_"
            "status_next_attempt"
        ),
        table_name=(
            "telegram_signal_deliveries"
        ),
    )

    op.drop_table(
        "telegram_signal_deliveries"
    )
