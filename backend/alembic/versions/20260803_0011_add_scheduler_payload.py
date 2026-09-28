"""Add persisted scheduler payload.

Revision ID: 20260803_0011
Revises: 20260803_0010
Create Date: 2026-08-03
"""

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260803_0011"
down_revision: Union[str, None] = (
    "20260803_0010"
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
        "scheduler_payload",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "configured",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "runtime_risk_payload",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "analysis_payload",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    payload_table = sa.table(
        "scheduler_payload",
        sa.column("id", sa.Integer()),
        sa.column("configured", sa.Boolean()),
        sa.column(
            "runtime_risk_payload",
            sa.JSON(),
        ),
        sa.column(
            "analysis_payload",
            sa.JSON(),
        ),
        sa.column(
            "updated_at",
            sa.DateTime(timezone=True),
        ),
    )

    op.bulk_insert(
        payload_table,
        [
            {
                "id": 1,
                "configured": False,
                "runtime_risk_payload": None,
                "analysis_payload": None,
                "updated_at": datetime.now(
                    timezone.utc
                ),
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("scheduler_payload")
