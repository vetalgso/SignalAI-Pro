"""Add Telegram signal lifecycle deliveries.

Revision ID: 20260828_0018
Revises: 20260827_0017
"""

from alembic import op
import sqlalchemy as sa


revision = "20260828_0018"
down_revision = "20260827_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "telegram_signal_deliveries",
        sa.Column(
            "delivery_type",
            sa.String(length=32),
            nullable=False,
            server_default=(
                "SIGNAL_CREATED"
            ),
        ),
    )

    op.add_column(
        "telegram_signal_deliveries",
        sa.Column(
            "event_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.drop_constraint(
        (
            "uq_telegram_signal_"
            "deliveries_signal_id"
        ),
        "telegram_signal_deliveries",
        type_="unique",
    )

    op.create_foreign_key(
        (
            "fk_telegram_signal_"
            "deliveries_event_id"
        ),
        "telegram_signal_deliveries",
        "trading_signal_events",
        ["event_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_unique_constraint(
        (
            "uq_telegram_signal_"
            "deliveries_event_id"
        ),
        "telegram_signal_deliveries",
        ["event_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        (
            "uq_telegram_signal_"
            "deliveries_event_id"
        ),
        "telegram_signal_deliveries",
        type_="unique",
    )

    op.drop_constraint(
        (
            "fk_telegram_signal_"
            "deliveries_event_id"
        ),
        "telegram_signal_deliveries",
        type_="foreignkey",
    )

    op.execute(
        sa.text(
            "DELETE FROM "
            "telegram_signal_deliveries "
            "WHERE delivery_type "
            "<> 'SIGNAL_CREATED'"
        )
    )

    op.drop_column(
        "telegram_signal_deliveries",
        "event_id",
    )
    op.drop_column(
        "telegram_signal_deliveries",
        "delivery_type",
    )

    op.create_unique_constraint(
        (
            "uq_telegram_signal_"
            "deliveries_signal_id"
        ),
        "telegram_signal_deliveries",
        ["signal_id"],
    )
