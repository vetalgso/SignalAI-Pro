"""Add scheduler runtime state.

Revision ID: 20260803_0010
Revises: 20260803_0009
Create Date: 2026-08-03
"""

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260803_0010"
down_revision: Union[str, None] = (
    "20260803_0009"
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
        "scheduler_state",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "interval_seconds",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "last_run_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "next_run_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_cycle_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "consecutive_failures",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    scheduler_state = sa.table(
        "scheduler_state",
        sa.column("id", sa.Integer()),
        sa.column("enabled", sa.Boolean()),
        sa.column(
            "interval_seconds",
            sa.Integer(),
        ),
        sa.column(
            "consecutive_failures",
            sa.Integer(),
        ),
        sa.column(
            "updated_at",
            sa.DateTime(timezone=True),
        ),
    )

    op.bulk_insert(
        scheduler_state,
        [
            {
                "id": 1,
                "enabled": False,
                "interval_seconds": 300,
                "consecutive_failures": 0,
                "updated_at": datetime.now(
                    timezone.utc
                ),
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("scheduler_state")
