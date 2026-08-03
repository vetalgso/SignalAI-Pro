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

        for symbol in symbols:
            try:
                prices[symbol] = (
                    await self._price_provider
                    .get_price(symbol)
                )
            except Exception as exc:
                price_errors[symbol] = str(exc)

        result = self._monitor_service.monitor(
            prices=prices,
            exchange=exchange,
        )

        return {
            **result,
            "requested_symbols": symbols,
            "prices": prices,
            "price_errors": price_errors,
        }
