from __future__ import annotations

from types import SimpleNamespace
from typing import Protocol

from app.models.trading_position import TradingPosition

from .manager import PositionManager
from .repository import TradingPositionRepository


class PreviewPriceProvider(Protocol):
    async def get_price(
        self,
        symbol: str,
    ) -> float:
        """Return the latest public market price."""


class _NoOpSession:
    def flush(self) -> None:
        return None


class _PreviewRepository:
    def __init__(self) -> None:
        self._session = _NoOpSession()


class LivePositionPreviewService:
    def __init__(
        self,
        *,
        position_repository: (
            TradingPositionRepository
        ),
        price_provider: PreviewPriceProvider,
    ) -> None:
        self._position_repository = (
            position_repository
        )
        self._price_provider = price_provider
        self._manager = PositionManager(
            repository=_PreviewRepository()
        )

    async def preview(
        self,
        *,
        exchange: str | None = None,
    ) -> dict[str, object]:
        positions = (
            self._position_repository.list_active(
                exchange=exchange,
                price_source="BINANCE_PUBLIC",
            )
        )

        symbols = sorted(
            {
                position.symbol
                for position in positions
            }
        )

        positions_by_symbol: dict[
            str,
            list[TradingPosition],
        ] = {}

        for position in positions:
            positions_by_symbol.setdefault(
                position.symbol,
                [],
            ).append(position)

        prices: dict[str, float] = {}
        price_errors: dict[str, str] = {}
        rejected_positions: list[
            dict[str, object]
        ] = []
        results: list[dict[str, object]] = []
        missing_symbols: set[str] = set()

        for symbol in symbols:
            try:
                market_price = float(
                    await self._price_provider
                    .get_price(symbol)
                )

                if market_price <= 0:
                    raise ValueError(
                        f"Price for {symbol} must be "
                        "greater than zero."
                    )

                prices[symbol] = market_price
            except Exception as exc:
                price_errors[symbol] = str(exc)
                missing_symbols.add(symbol)
                continue

            for position in positions_by_symbol[
                symbol
            ]:
                entry_price = float(
                    position.entry_price
                )
                maximum = float(
                    position
                    .max_price_deviation_percent
                )
                deviation = (
                    abs(
                        market_price - entry_price
                    )
                    / entry_price
                    * 100
                )

                if deviation > maximum:
                    rejected_positions.append(
                        {
                            "position_id": position.id,
                            "symbol": symbol,
                            "entry_price": entry_price,
                            "market_price": (
                                market_price
                            ),
                            "deviation_percent": round(
                                deviation,
                                8,
                            ),
                            "maximum_percent": maximum,
                            "reason": (
                                "PRICE_DEVIATION_LIMIT"
                            ),
                        }
                    )
                    continue

                preview_position = (
                    self._clone_position(position)
                )

                result = self._manager.update_price(
                    position=preview_position,
                    current_price=market_price,
                )

                result["preview_only"] = True
                result["original_status"] = (
                    position.status
                )
                result[
                    "original_remaining_quantity"
                ] = float(
                    position.remaining_quantity
                )
                result["original_realized_pnl"] = (
                    float(position.realized_pnl)
                )
                result["original_unrealized_pnl"] = (
                    float(position.unrealized_pnl)
                )

                results.append(result)

        return {
            "preview_only": True,
            "checked_positions": len(positions),
            "previewed_positions": len(results),
            "missing_symbols": sorted(
                missing_symbols
            ),
            "requested_symbols": symbols,
            "prices": prices,
            "price_errors": price_errors,
            "rejected_positions": (
                rejected_positions
            ),
            "results": results,
        }

    @staticmethod
    def _clone_position(
        position: TradingPosition,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            id=position.id,
            journal_order_id=(
                position.journal_order_id
            ),
            exchange=position.exchange,
            market_type=position.market_type,
            symbol=position.symbol,
            side=position.side,
            status=position.status,
            price_source=position.price_source,
            max_price_deviation_percent=(
                position
                .max_price_deviation_percent
            ),
            initial_quantity=(
                position.initial_quantity
            ),
            remaining_quantity=(
                position.remaining_quantity
            ),
            closed_quantity=(
                position.closed_quantity
            ),
            entry_price=position.entry_price,
            current_price=position.current_price,
            exit_price=position.exit_price,
            stop_loss=position.stop_loss,
            take_profit_1=(
                position.take_profit_1
            ),
            take_profit_2=(
                position.take_profit_2
            ),
            tp1_close_percent=(
                position.tp1_close_percent
            ),
            tp1_triggered=position.tp1_triggered,
            tp2_triggered=position.tp2_triggered,
            break_even_activated=(
                position.break_even_activated
            ),
            stop_loss_triggered=(
                position.stop_loss_triggered
            ),
            realized_pnl=position.realized_pnl,
            unrealized_pnl=(
                position.unrealized_pnl
            ),
            metadata_payload=dict(
                position.metadata_payload or {}
            ),
            opened_at=position.opened_at,
            updated_at=position.updated_at,
            closed_at=position.closed_at,
        )
