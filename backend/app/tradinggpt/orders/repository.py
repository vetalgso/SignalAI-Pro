from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.trading_order import TradingOrder


class TradingOrderRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

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
        return self._session.get(
            TradingOrder,
            order_id,
        )

    def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> TradingOrder | None:
        statement = select(TradingOrder).where(
            TradingOrder.idempotency_key
            == idempotency_key
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
        statement = select(TradingOrder)

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

    def apply_preview(
        self,
        order: TradingOrder,
        *,
        valid: bool,
        normalized_quantity: float,
        normalized_price: float | None,
        preview_payload: dict[str, Any],
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
