from __future__ import annotations

from typing import Protocol

from app.services.binance_market import BinanceMarketService

from .monitor import PositionMonitorService
from .repository import TradingPositionRepository


class LivePriceProvider(Protocol):
    async def get_price(
        self,
        symbol: str,
    ) -> float:
        """Return the latest public market price."""


class BinanceLivePriceProvider:
    def __init__(
        self,
        service: BinanceMarketService | None = None,
    ) -> None:
        self._service = (
            service or BinanceMarketService()
        )

    async def get_price(
        self,
        symbol: str,
    ) -> float:
        payload = await self._service.ticker_price(
            symbol.upper()
        )

        price = float(payload["price"])

        if price <= 0:
            raise ValueError(
                f"Binance returned an invalid price "
                f"for {symbol.upper()}."
            )

        return price


class LivePositionMonitorService:
    def __init__(
        self,
        *,
        position_repository: (
            TradingPositionRepository
        ),
        monitor_service: PositionMonitorService,
        price_provider: LivePriceProvider,
    ) -> None:
        self._position_repository = (
            position_repository
        )
        self._monitor_service = monitor_service
        self._price_provider = price_provider

    async def monitor(
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

        prices: dict[str, float] = {}
        price_errors: dict[str, str] = {}
        rejected_positions: list[
            dict[str, object]
        ] = []

        positions_by_symbol: dict[
            str,
            list[object],
        ] = {}

        for position in positions:
            positions_by_symbol.setdefault(
                position.symbol,
                [],
            ).append(position)

        for symbol in symbols:
            try:
                candidate_price = (
                    await self._price_provider
                    .get_price(symbol)
                )

                accepted = True

                for position in positions_by_symbol[
                    symbol
                ]:
                    entry_price = float(
                        position.entry_price
                    )
                    deviation = abs(
                        candidate_price - entry_price
                    ) / entry_price * 100
                    maximum = float(
                        position
                        .max_price_deviation_percent
                    )

                    if deviation > maximum:
                        accepted = False
                        rejected_positions.append(
                            {
                                "position_id": (
                                    position.id
                                ),
                                "symbol": symbol,
                                "entry_price": (
                                    entry_price
                                ),
                                "market_price": (
                                    candidate_price
                                ),
                                "deviation_percent": (
                                    round(
                                        deviation,
                                        8,
                                    )
                                ),
                                "maximum_percent": (
                                    maximum
                                ),
                                "reason": (
                                    "PRICE_DEVIATION_LIMIT"
                                ),
                            }
                        )

                if accepted:
                    prices[symbol] = (
                        candidate_price
                    )
                else:
                    price_errors[symbol] = (
                        "Market price exceeded the "
                        "configured deviation limit."
                    )
            except Exception as exc:
                price_errors[symbol] = str(exc)

        result = self._monitor_service.monitor(
            prices=prices,
            exchange=exchange,
            price_source="BINANCE_PUBLIC",
        )

        return {
            **result,
            "requested_symbols": symbols,
            "prices": prices,
            "price_errors": price_errors,
            "rejected_positions": (
                rejected_positions
            ),
        }
