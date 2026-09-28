"""Add position lifecycle events.

Revision ID: 20260803_0007
Revises: 20260803_0006
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260803_0007"
down_revision: Union[str, None] = (
    "20260803_0006"
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
        "position_events",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "position_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(length=48),
            nullable=False,
        ),
        sa.Column(
            "price",
            sa.Numeric(30, 12),
            nullable=True,
        ),
        sa.Column(
            "payload",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    for column in (
        "position_id",
        "event_type",
        "created_at",
    ):
        op.create_index(
            op.f(
                f"ix_position_events_{column}"
            ),
            "position_events",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in (
        "created_at",
        "event_type",
        "position_id",
    ):
        op.drop_index(
            op.f(
                f"ix_position_events_{column}"
            ),
            table_name="position_events",
        )

    op.drop_table("position_events")
