from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.trading_position import TradingPosition


class TradingPositionRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def create(
        self,
        *,
        exchange: str,
        market_type: str,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        stop_loss: float | None,
        take_profit_1: float | None,
        take_profit_2: float | None,
        journal_order_id: int | None = None,
        tp1_close_percent: float = 50.0,
        price_source: str = "MANUAL",
        max_price_deviation_percent: float = 25.0,
        metadata_payload: dict[str, Any] | None = None,
    ) -> TradingPosition:
        position = TradingPosition(
            journal_order_id=journal_order_id,
            exchange=exchange.upper(),
            market_type=market_type.upper(),
            symbol=symbol.upper(),
            side=side.upper(),
            status="OPEN",
            price_source=price_source.upper(),
            max_price_deviation_percent=Decimal(
                str(max_price_deviation_percent)
            ),
            initial_quantity=Decimal(str(quantity)),
            remaining_quantity=Decimal(str(quantity)),
            closed_quantity=Decimal("0"),
            entry_price=Decimal(str(entry_price)),
            current_price=Decimal(str(entry_price)),
            stop_loss=(
                Decimal(str(stop_loss))
                if stop_loss is not None
                else None
            ),
            take_profit_1=(
                Decimal(str(take_profit_1))
                if take_profit_1 is not None
                else None
            ),
            take_profit_2=(
                Decimal(str(take_profit_2))
                if take_profit_2 is not None
                else None
            ),
            tp1_close_percent=Decimal(
                str(tp1_close_percent)
            ),
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            metadata_payload=metadata_payload or {},
        )

        self._session.add(position)
        self._session.flush()

        return position

    def get(
        self,
        position_id: int,
    ) -> TradingPosition | None:
        return self._session.get(
            TradingPosition,
            position_id,
        )

    def get_by_journal_order_id(
        self,
        journal_order_id: int,
    ) -> TradingPosition | None:
        statement = select(TradingPosition).where(
            TradingPosition.journal_order_id
            == journal_order_id
        )

        return self._session.scalar(statement)

    def list_positions(
        self,
        *,
        status: str | None = None,
        exchange: str | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[TradingPosition]:
        statement = select(TradingPosition)

        if status is not None:
            statement = statement.where(
                TradingPosition.status
                == status.upper()
            )

        if exchange is not None:
            statement = statement.where(
                TradingPosition.exchange
                == exchange.upper()
            )

        if symbol is not None:
            statement = statement.where(
                TradingPosition.symbol
                == symbol.upper()
            )

        statement = statement.order_by(
            TradingPosition.id.desc()
        ).limit(limit)

        return list(
            self._session.scalars(statement)
        )

    def list_active(
        self,
        *,
        exchange: str | None = None,
        symbol: str | None = None,
        price_source: str | None = None,
    ) -> list[TradingPosition]:
        statement = select(TradingPosition).where(
            TradingPosition.status.in_(
                ["OPEN", "PARTIALLY_CLOSED"]
            )
        )

        if exchange is not None:
            statement = statement.where(
                TradingPosition.exchange
                == exchange.upper()
            )

        if symbol is not None:
            statement = statement.where(
                TradingPosition.symbol
                == symbol.upper()
            )

        if price_source is not None:
            statement = statement.where(
                TradingPosition.price_source
                == price_source.upper()
            )

        statement = statement.order_by(
            TradingPosition.id.asc()
        )

        return list(
            self._session.scalars(statement)
        )
