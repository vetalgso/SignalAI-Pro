from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.exchange_account import (
    ExchangeAccount,
)


class ExchangeAccountRepository:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def list_for_user(
        self,
        user_id: int,
    ) -> list[ExchangeAccount]:
        statement = (
            select(ExchangeAccount)
            .where(
                ExchangeAccount.user_id
                == user_id
            )
            .order_by(
                ExchangeAccount.created_at.asc(),
                ExchangeAccount.id.asc(),
            )
        )

        return list(
            self.db.scalars(
                statement
            ).all()
        )

    def get_for_user(
        self,
        *,
        account_id: int,
        user_id: int,
    ) -> ExchangeAccount | None:
        statement = select(
            ExchangeAccount
        ).where(
            ExchangeAccount.id
            == account_id,
            ExchangeAccount.user_id
            == user_id,
        )

        return self.db.scalar(statement)

    def get_by_scope(
        self,
        *,
        user_id: int,
        exchange: str,
        environment: str,
    ) -> ExchangeAccount | None:
        statement = select(
            ExchangeAccount
        ).where(
            ExchangeAccount.user_id
            == user_id,
            ExchangeAccount.exchange
            == exchange,
            ExchangeAccount.environment
            == environment,
        )

        return self.db.scalar(statement)

    def add(
        self,
        account: ExchangeAccount,
    ) -> ExchangeAccount:
        self.db.add(account)
        self.db.flush()

        return account

    def save(
        self,
        account: ExchangeAccount,
    ) -> ExchangeAccount:
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)

        return account

    def delete(
        self,
        account: ExchangeAccount,
    ) -> None:
        self.db.delete(account)
        self.db.commit()
