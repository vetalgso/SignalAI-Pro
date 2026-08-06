"""Add user-scoped trading orders.

Revision ID: 20260806_0014
Revises: 20260805_0013
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260806_0014"
down_revision: str | None = "20260805_0013"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trading_orders",
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "trading_orders",
        sa.Column(
            "exchange_account_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_trading_orders_user_id_users",
        "trading_orders",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_foreign_key(
        (
            "fk_trading_orders_"
            "exchange_account_id_"
            "exchange_accounts"
        ),
        "trading_orders",
        "exchange_accounts",
        ["exchange_account_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_trading_orders_user_id",
        "trading_orders",
        ["user_id"],
        unique=False,
    )

    op.create_index(
        (
            "ix_trading_orders_"
            "exchange_account_id"
        ),
        "trading_orders",
        ["exchange_account_id"],
        unique=False,
    )

    op.drop_index(
        "ix_trading_orders_idempotency_key",
        table_name="trading_orders",
    )

    op.drop_constraint(
        "trading_orders_idempotency_key_key",
        "trading_orders",
        type_="unique",
    )

    op.create_index(
        "ix_trading_orders_idempotency_key",
        "trading_orders",
        ["idempotency_key"],
        unique=False,
    )

    op.create_unique_constraint(
        (
            "uq_trading_orders_"
            "user_id_idempotency_key"
        ),
        "trading_orders",
        [
            "user_id",
            "idempotency_key",
        ],
    )

    op.create_index(
        (
            "uq_trading_orders_"
            "system_idempotency_key"
        ),
        "trading_orders",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text(
            "user_id IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        (
            "uq_trading_orders_"
            "system_idempotency_key"
        ),
        table_name="trading_orders",
    )

    op.drop_constraint(
        (
            "uq_trading_orders_"
            "user_id_idempotency_key"
        ),
        "trading_orders",
        type_="unique",
    )

    op.drop_index(
        "ix_trading_orders_idempotency_key",
        table_name="trading_orders",
    )

    op.create_unique_constraint(
        "trading_orders_idempotency_key_key",
        "trading_orders",
        ["idempotency_key"],
    )

    op.create_index(
        "ix_trading_orders_idempotency_key",
        "trading_orders",
        ["idempotency_key"],
        unique=True,
    )

    op.drop_index(
        (
            "ix_trading_orders_"
            "exchange_account_id"
        ),
        table_name="trading_orders",
    )

    op.drop_index(
        "ix_trading_orders_user_id",
        table_name="trading_orders",
    )

    op.drop_constraint(
        (
            "fk_trading_orders_"
            "exchange_account_id_"
            "exchange_accounts"
        ),
        "trading_orders",
        type_="foreignkey",
    )

    op.drop_constraint(
        "fk_trading_orders_user_id_users",
        "trading_orders",
        type_="foreignkey",
    )

    op.drop_column(
        "trading_orders",
        "exchange_account_id",
    )

    op.drop_column(
        "trading_orders",
        "user_id",
    )

