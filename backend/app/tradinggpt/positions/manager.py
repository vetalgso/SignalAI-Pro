from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN

from app.models.trading_position import TradingPosition

from .repository import TradingPositionRepository


class PositionManager:
    def __init__(
        self,
        *,
        repository: TradingPositionRepository,
    ) -> None:
        self._repository = repository

    def update_price(
        self,
        *,
        position: TradingPosition,
        current_price: float,
    ) -> dict[str, object]:
        if position.status == "CLOSED":
            return self.serialize(
                position,
                actions=["ALREADY_CLOSED"],
            )

        price = Decimal(str(current_price))

        if price <= 0:
            raise ValueError(
                "Current price must be greater than zero."
            )

        position.current_price = price
        actions: list[str] = []

        self._update_unrealized_pnl(position)

        if self._stop_loss_reached(position, price):
            self._close_remaining(
                position=position,
                exit_price=price,
                reason="STOP_LOSS",
            )
            actions.append("STOP_LOSS")
        else:
            if (
                not position.tp1_triggered
                and self._tp1_reached(position, price)
            ):
                self._apply_tp1(
                    position=position,
                    exit_price=price,
                )
                actions.extend(
                    [
                        "TAKE_PROFIT_1",
                        "BREAK_EVEN",
                    ]
                )

            if (
                position.status != "CLOSED"
                and not position.tp2_triggered
                and self._tp2_reached(position, price)
            ):
                self._close_remaining(
                    position=position,
                    exit_price=price,
                    reason="TAKE_PROFIT_2",
                )
                position.tp2_triggered = True
                actions.append("TAKE_PROFIT_2")

        self._repository._session.flush()

        return self.serialize(
            position,
            actions=actions or ["PRICE_UPDATED"],
        )

    def close_manually(
        self,
        *,
        position: TradingPosition,
        exit_price: float,
    ) -> dict[str, object]:
        if position.status == "CLOSED":
            return self.serialize(
                position,
                actions=["ALREADY_CLOSED"],
            )

        price = Decimal(str(exit_price))

        if price <= 0:
            raise ValueError(
                "Exit price must be greater than zero."
            )

        self._close_remaining(
            position=position,
            exit_price=price,
            reason="MANUAL_CLOSE",
        )
        self._repository._session.flush()

        return self.serialize(
            position,
            actions=["MANUAL_CLOSE"],
        )

    def _apply_tp1(
        self,
        *,
        position: TradingPosition,
        exit_price: Decimal,
    ) -> None:
        percentage = (
            position.tp1_close_percent
            / Decimal("100")
        )
        quantity_to_close = (
            position.initial_quantity * percentage
        ).quantize(
            Decimal("0.000000000001"),
            rounding=ROUND_DOWN,
        )

        quantity_to_close = min(
            quantity_to_close,
            position.remaining_quantity,
        )

        pnl = self._calculate_pnl(
            position=position,
            quantity=quantity_to_close,
            exit_price=exit_price,
        )

        position.realized_pnl += pnl
        position.remaining_quantity -= (
            quantity_to_close
        )
        position.closed_quantity += (
            quantity_to_close
        )
        position.tp1_triggered = True
        position.break_even_activated = True
        position.stop_loss = position.entry_price

        if position.remaining_quantity <= 0:
            position.remaining_quantity = Decimal("0")
            position.status = "CLOSED"
            position.exit_price = exit_price
            position.closed_at = datetime.now(
                timezone.utc
            )
        else:
            position.status = "PARTIALLY_CLOSED"

        self._update_unrealized_pnl(position)

    def _close_remaining(
        self,
        *,
        position: TradingPosition,
        exit_price: Decimal,
        reason: str,
    ) -> None:
        quantity = position.remaining_quantity

        pnl = self._calculate_pnl(
            position=position,
            quantity=quantity,
            exit_price=exit_price,
        )

        position.realized_pnl += pnl
        position.closed_quantity += quantity
        position.remaining_quantity = Decimal("0")
        position.unrealized_pnl = Decimal("0")
        position.current_price = exit_price
        position.exit_price = exit_price
        position.status = "CLOSED"
        position.closed_at = datetime.now(
            timezone.utc
        )

        if reason == "STOP_LOSS":
            position.stop_loss_triggered = True

        metadata = dict(
            position.metadata_payload or {}
        )
        metadata["close_reason"] = reason
        position.metadata_payload = metadata

    @staticmethod
    def _calculate_pnl(
        *,
        position: TradingPosition,
        quantity: Decimal,
        exit_price: Decimal,
    ) -> Decimal:
        difference = (
            exit_price - position.entry_price
            if position.side == "LONG"
            else position.entry_price - exit_price
        )

        return difference * quantity

    def _update_unrealized_pnl(
        self,
        position: TradingPosition,
    ) -> None:
        position.unrealized_pnl = (
            self._calculate_pnl(
                position=position,
                quantity=position.remaining_quantity,
                exit_price=position.current_price,
            )
            if position.remaining_quantity > 0
            else Decimal("0")
        )

    @staticmethod
    def _stop_loss_reached(
        position: TradingPosition,
        price: Decimal,
    ) -> bool:
        if position.stop_loss is None:
            return False

        if position.side == "LONG":
            return price <= position.stop_loss

        return price >= position.stop_loss

    @staticmethod
    def _tp1_reached(
        position: TradingPosition,
        price: Decimal,
    ) -> bool:
        if position.take_profit_1 is None:
            return False

        if position.side == "LONG":
            return price >= position.take_profit_1

        return price <= position.take_profit_1

    @staticmethod
    def _tp2_reached(
        position: TradingPosition,
        price: Decimal,
    ) -> bool:
        if position.take_profit_2 is None:
            return False

        if position.side == "LONG":
            return price >= position.take_profit_2

        return price <= position.take_profit_2

    @staticmethod
    def serialize(
        position: TradingPosition,
        *,
        actions: list[str] | None = None,
    ) -> dict[str, object]:
        return {
            "id": position.id,
            "journal_order_id": (
                position.journal_order_id
            ),
            "exchange": position.exchange,
            "market_type": position.market_type,
            "symbol": position.symbol,
            "side": position.side,
            "status": position.status,
            "price_source": position.price_source,
            "max_price_deviation_percent": float(
                position.max_price_deviation_percent
            ),
            "initial_quantity": float(
                position.initial_quantity
            ),
            "remaining_quantity": float(
                position.remaining_quantity
            ),
            "closed_quantity": float(
                position.closed_quantity
            ),
            "entry_price": float(
                position.entry_price
            ),
            "current_price": float(
                position.current_price
            ),
            "exit_price": (
                float(position.exit_price)
                if position.exit_price is not None
                else None
            ),
            "stop_loss": (
                float(position.stop_loss)
                if position.stop_loss is not None
                else None
            ),
            "take_profit_1": (
                float(position.take_profit_1)
                if position.take_profit_1
                is not None
                else None
            ),
            "take_profit_2": (
                float(position.take_profit_2)
                if position.take_profit_2
                is not None
                else None
            ),
            "tp1_triggered": (
                position.tp1_triggered
            ),
            "tp2_triggered": (
                position.tp2_triggered
            ),
            "break_even_activated": (
                position.break_even_activated
            ),
            "stop_loss_triggered": (
                position.stop_loss_triggered
            ),
            "realized_pnl": float(
                position.realized_pnl
            ),
            "unrealized_pnl": float(
                position.unrealized_pnl
            ),
            "metadata_payload": (
                position.metadata_payload
            ),
            "opened_at": position.opened_at,
            "updated_at": position.updated_at,
            "closed_at": position.closed_at,
            "actions": actions or [],
        }
