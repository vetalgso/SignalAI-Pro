"""Add scheduler cycle journal.

Revision ID: 20260803_0009
Revises: 20260803_0008
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260803_0009"
down_revision: Union[str, None] = (
    "20260803_0008"
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
        "scheduler_cycles",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "dry_run",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "risk_payload",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "execution_payload",
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
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_scheduler_cycles_status",
        "scheduler_cycles",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_scheduler_cycles_started_at",
        "scheduler_cycles",
        ["started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_scheduler_cycles_started_at",
        table_name="scheduler_cycles",
    )
    op.drop_index(
        "ix_scheduler_cycles_status",
        table_name="scheduler_cycles",
    )
    op.drop_table("scheduler_cycles")
