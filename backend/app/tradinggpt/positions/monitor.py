from __future__ import annotations

from typing import Mapping

from .event_repository import PositionEventRepository
from .manager import PositionManager
from .repository import TradingPositionRepository


class PositionMonitorService:
    def __init__(
        self,
        *,
        position_repository: TradingPositionRepository,
        event_repository: PositionEventRepository,
    ) -> None:
        self._position_repository = (
            position_repository
        )
        self._event_repository = event_repository
        self._manager = PositionManager(
            repository=position_repository
        )

    def monitor(
        self,
        *,
        prices: Mapping[str, float],
        exchange: str | None = None,
        price_source: str | None = None,
    ) -> dict[str, object]:
        normalized_prices = {
            symbol.upper(): float(price)
            for symbol, price in prices.items()
        }

        for symbol, price in normalized_prices.items():
            if price <= 0:
                raise ValueError(
                    f"Price for {symbol} must be "
                    "greater than zero."
                )

        positions = (
            self._position_repository.list_active(
                exchange=exchange,
                price_source=price_source,
            )
        )

        results: list[dict[str, object]] = []
        missing_symbols: set[str] = set()

        for position in positions:
            price = normalized_prices.get(
                position.symbol
            )

            if price is None:
                missing_symbols.add(
                    position.symbol
                )
                continue

            before_status = position.status
            before_remaining = float(
                position.remaining_quantity
            )
            before_stop_loss = (
                float(position.stop_loss)
                if position.stop_loss is not None
                else None
            )

            result = self._manager.update_price(
                position=position,
                current_price=price,
            )

            actions = list(result["actions"])

            for action in actions:
                self._event_repository.create(
                    position_id=position.id,
                    event_type=action,
                    price=price,
                    payload={
                        "symbol": position.symbol,
                        "exchange": position.exchange,
                        "status_before": before_status,
                        "status_after": (
                            position.status
                        ),
                        "remaining_before": (
                            before_remaining
                        ),
                        "remaining_after": float(
                            position.remaining_quantity
                        ),
                        "stop_loss_before": (
                            before_stop_loss
                        ),
                        "stop_loss_after": (
                            float(position.stop_loss)
                            if position.stop_loss
                            is not None
                            else None
                        ),
                        "realized_pnl": float(
                            position.realized_pnl
                        ),
                        "unrealized_pnl": float(
                            position.unrealized_pnl
                        ),
                    },
                )

            results.append(result)

        self._position_repository._session.commit()

        return {
            "checked_positions": len(positions),
            "updated_positions": len(results),
            "missing_symbols": sorted(
                missing_symbols
            ),
            "results": results,
        }

    def list_events(
        self,
        *,
        position_id: int | None,
        event_type: str | None,
        limit: int,
    ) -> list[dict[str, object]]:
        events = self._event_repository.list_events(
            position_id=position_id,
            event_type=event_type,
            limit=limit,
        )

        return [
            self.serialize_event(event)
            for event in events
        ]

    @staticmethod
    def serialize_event(
        event: object,
    ) -> dict[str, object]:
        return {
            "id": event.id,
            "position_id": event.position_id,
            "event_type": event.event_type,
            "price": (
                float(event.price)
                if event.price is not None
                else None
            ),
            "payload": event.payload,
            "created_at": event.created_at,
        }
