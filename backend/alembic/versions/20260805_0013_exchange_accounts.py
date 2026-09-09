from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260805_0013"
down_revision: str | None = "20260804_0012"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exchange_accounts",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey(
                "users.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "exchange",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "environment",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "label",
            sa.String(length=80),
            nullable=False,
        ),
        sa.Column(
            "encrypted_api_key",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "encrypted_secret_key",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "api_key_hint",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
        ),
        sa.Column(
            "can_trade",
            sa.Boolean(),
            nullable=True,
        ),
        sa.Column(
            "can_deposit",
            sa.Boolean(),
            nullable=True,
        ),
        sa.Column(
            "can_withdraw",
            sa.Boolean(),
            nullable=True,
        ),
        sa.Column(
            "last_checked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_error",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
        ),
        sa.UniqueConstraint(
            "user_id",
            "exchange",
            "environment",
            name=(
                "uq_exchange_accounts_"
                "user_exchange_environment"
            ),
        ),
    )

    op.create_index(
        "ix_exchange_accounts_user_id",
        "exchange_accounts",
        ["user_id"],
        unique=False,
    )

    op.create_index(
        "ix_exchange_accounts_status",
        "exchange_accounts",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_exchange_accounts_status",
        table_name="exchange_accounts",
    )

    op.drop_index(
        "ix_exchange_accounts_user_id",
        table_name="exchange_accounts",
    )

    op.drop_table("exchange_accounts")
