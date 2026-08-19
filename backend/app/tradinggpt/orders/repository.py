from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.exchange_account import (
    ExchangeAccount,
)
from app.models.trading_order import TradingOrder

from .risk import OrderRiskUsage


RISK_NOTIONAL_STATUSES = (
    "FILLED",
    "OPEN",
    "PARTIALLY_FILLED",
)
OPEN_ORDER_STATUSES = (
    "OPEN",
    "PARTIALLY_FILLED",
)


class TradingOrderRepository:
    def __init__(
        self,
        session: Session,
        *,
        user_id: int | None = None,
        exchange_account_id: (
            int | None
        ) = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._exchange_account_id = (
            exchange_account_id
        )

    def create(
        self,
        *,
        idempotency_key: str,
        exchange: str,
        market_type: str,
        symbol: str,
        side: str,
        order_type: str,
        requested_quantity: float,
        requested_price: float | None,
        dry_run: bool,
        request_payload: dict[str, Any],
        status: str = "PENDING",
    ) -> TradingOrder:
        order = TradingOrder(
            user_id=self._user_id,
            exchange_account_id=(
                self._exchange_account_id
            ),
            idempotency_key=idempotency_key,
            exchange=exchange,
            market_type=market_type,
            symbol=symbol,
            side=side,
            order_type=order_type,
            status=status,
            requested_quantity=Decimal(
                str(requested_quantity)
            ),
            requested_price=(
                Decimal(str(requested_price))
                if requested_price is not None
                else None
            ),
            dry_run=dry_run,
            request_payload=request_payload,
        )

        self._session.add(order)
        self._session.flush()

        return order

    def get_by_id(
        self,
        order_id: int,
    ) -> TradingOrder | None:
        statement = select(
            TradingOrder
        ).where(
            TradingOrder.id == order_id,
            *self._ownership_scope(),
        )

        return self._session.scalar(
            statement
        )

    def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> TradingOrder | None:
        statement = select(TradingOrder).where(
            TradingOrder.idempotency_key
            == idempotency_key,
            self._user_scope(),
        )

        return self._session.scalar(statement)

    def list_recent(
        self,
        *,
        limit: int = 50,
        exchange: str | None = None,
        symbol: str | None = None,
        status: str | None = None,
    ) -> list[TradingOrder]:
        statement = select(
            TradingOrder
        ).where(
            *self._ownership_scope()
        )

        if exchange is not None:
            statement = statement.where(
                TradingOrder.exchange == exchange
            )

        if symbol is not None:
            statement = statement.where(
                TradingOrder.symbol == symbol
            )

        if status is not None:
            statement = statement.where(
                TradingOrder.status == status
            )

        statement = statement.order_by(
            TradingOrder.id.desc()
        ).limit(limit)

        return list(
            self._session.scalars(statement)
        )

    def lock_risk_scope(self) -> None:
        user_id, account_id = (
            self._require_account_scope()
        )

        statement = (
            select(ExchangeAccount.id)
            .where(
                ExchangeAccount.id
                == account_id,
                ExchangeAccount.user_id
                == user_id,
            )
            .with_for_update()
        )

        if self._session.scalar(
            statement
        ) is None:
            raise ValueError(
                "Exchange account risk scope "
                "was not found."
            )

    def get_risk_usage(
        self,
        *,
        since: datetime,
    ) -> OrderRiskUsage:
        self._require_account_scope()

        daily_statement = select(
            func.coalesce(
                func.sum(
                    TradingOrder
                    .estimated_notional
                ),
                0,
            )
        ).where(
            *self._ownership_scope(),
            TradingOrder.dry_run.is_(False),
            TradingOrder.created_at >= since,
            TradingOrder.status.in_(
                RISK_NOTIONAL_STATUSES
            ),
        )

        open_statement = select(
            func.count(TradingOrder.id)
        ).where(
            *self._ownership_scope(),
            TradingOrder.dry_run.is_(False),
            TradingOrder.status.in_(
                OPEN_ORDER_STATUSES
            ),
        )

        daily_notional = (
            self._session.scalar(
                daily_statement
            )
        )
        open_orders = self._session.scalar(
            open_statement
        )

        return OrderRiskUsage(
            daily_notional=float(
                daily_notional or 0
            ),
            open_orders=int(
                open_orders or 0
            ),
        )

    def get_today_risk_usage(
        self,
        *,
        now: datetime | None = None,
    ) -> OrderRiskUsage:
        reference = (
            now
            or datetime.now(timezone.utc)
        )
        since = reference.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        return self.get_risk_usage(
            since=since
        )

    def _require_account_scope(
        self,
    ) -> tuple[int, int]:
        if (
            self._user_id is None
            or self._exchange_account_id
            is None
        ):
            raise ValueError(
                "User and exchange account "
                "scope are required."
            )

        return (
            self._user_id,
            self._exchange_account_id,
        )

    def _ownership_scope(
        self,
    ) -> tuple[Any, ...]:
        predicates = [
            self._user_scope()
        ]

        if (
            self._exchange_account_id
            is not None
        ):
            predicates.append(
                TradingOrder
                .exchange_account_id
                == self._exchange_account_id
            )

        return tuple(predicates)

    def _user_scope(
        self,
    ) -> Any:
        if self._user_id is None:
            return (
                TradingOrder.user_id
                .is_(None)
            )

        return (
            TradingOrder.user_id
            == self._user_id
        )

    def apply_preview(
        self,
        order: TradingOrder,
        *,
        valid: bool,
        normalized_quantity: float,
        normalized_price: float | None,
        preview_payload: dict[str, Any],
        estimated_notional: (
            float | None
        ) = None,
        error_message: str | None = None,
    ) -> TradingOrder:
        order.normalized_quantity = Decimal(
            str(normalized_quantity)
        )
        order.normalized_price = (
            Decimal(str(normalized_price))
            if normalized_price is not None
            else None
        )
        order.preview_payload = preview_payload
        order.estimated_notional = (
            Decimal(str(estimated_notional))
            if estimated_notional is not None
            else None
        )
        order.status = (
            "PREVIEWED"
            if valid
            else "VALIDATION_FAILED"
        )
        order.error_message = error_message

        self._session.flush()

        return order

    def apply_execution(
        self,
        order: TradingOrder,
        *,
        status: str,
        client_order_id: str | None,
        exchange_order_id: str | None,
        filled_quantity: float,
        average_price: float | None,
        simulated: bool,
        execution_payload: dict[str, Any],
        error_message: str | None = None,
    ) -> TradingOrder:
        order.status = status
        order.client_order_id = client_order_id
        order.exchange_order_id = exchange_order_id
        order.filled_quantity = Decimal(
            str(filled_quantity)
        )
        order.average_price = (
            Decimal(str(average_price))
            if average_price is not None
            else None
        )
        order.simulated = simulated
        order.execution_payload = execution_payload
        order.error_message = error_message

        self._session.flush()

        return order
