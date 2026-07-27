from __future__ import annotations

from collections.abc import Callable

from app.tradinggpt.orders.adapters import (
    BinanceOrderAdapter,
    ExchangeOrderAdapter,
    PaperOrderAdapter,
)
from app.tradinggpt.orders.execution_service import (
    OrderExecutionService,
)

from .client_factory import create_binance_client
from .config import ExchangeExecutionSettings


BinanceClientFactory = Callable[
    [ExchangeExecutionSettings],
    object | None,
]


class ExchangeAdapterRegistry:
    def __init__(
        self,
        *,
        settings: ExchangeExecutionSettings | None = None,
        binance_client_factory: BinanceClientFactory | None = None,
    ) -> None:
        self._settings = (
            settings
            if settings is not None
            else ExchangeExecutionSettings.from_env()
        )
        self._binance_client_factory = (
            binance_client_factory
            if binance_client_factory is not None
            else self._create_default_binance_client
        )

    def build_adapters(
        self,
    ) -> list[ExchangeOrderAdapter]:
        adapters: list[ExchangeOrderAdapter] = [
            PaperOrderAdapter(),
        ]

        if not self._settings.enable_binance_execution:
            return adapters

        self._settings.validate_binance_activation()

        client = self._binance_client_factory(
            self._settings
        )

        if client is None:
            raise RuntimeError(
                "Binance execution is enabled, but "
                "the client factory returned no client."
            )

        adapters.append(
            BinanceOrderAdapter(
                client=client,
                testnet=self._settings.binance_testnet,
            )
        )

        return adapters

    def build_execution_service(
        self,
    ) -> OrderExecutionService:
        return OrderExecutionService(
            adapters=self.build_adapters()
        )

    @staticmethod
    def _create_default_binance_client(
        settings: ExchangeExecutionSettings,
    ) -> object | None:
        return create_binance_client(
            settings=settings
        )


def create_order_execution_service(
    *,
    settings: ExchangeExecutionSettings | None = None,
) -> OrderExecutionService:
    return ExchangeAdapterRegistry(
        settings=settings
    ).build_execution_service()
