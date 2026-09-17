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
from app.tradinggpt.portfolio_sync.binance import (
    BinancePortfolioProvider,
)
from app.tradinggpt.portfolio_sync.paper import (
    PaperPortfolioProvider,
)
from app.tradinggpt.portfolio_sync.service import (
    PortfolioSyncService,
)

from .client_factory import create_binance_client
from .config import ExchangeExecutionSettings


BinanceClientFactory = Callable[
    [ExchangeExecutionSettings],
    object | None,
]


class ExchangeAdapterRegistry:
    """
    Build exchange-backed TradingGPT services.

    The registry is the single composition point for:
    - order execution adapters;
    - portfolio synchronization providers;
    - Binance client creation and safety validation.
    """

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
        self._binance_client: object | None = None
        self._binance_client_initialized = False

    def build_adapters(
        self,
    ) -> list[ExchangeOrderAdapter]:
        adapters: list[ExchangeOrderAdapter] = [
            PaperOrderAdapter(),
        ]

        client = self._get_enabled_binance_client()

        if client is None:
            return adapters

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

    def build_portfolio_providers(
        self,
    ) -> list[object]:
        """
        Build portfolio providers using the same exchange client and
        activation rules as order execution.

        PAPER is always available. BINANCE is registered only when
        Binance integration has been explicitly enabled and validated.
        """

        providers: list[object] = [
            PaperPortfolioProvider(),
        ]

        client = self._get_enabled_binance_client()

        if client is None:
            return providers

        providers.append(
            BinancePortfolioProvider(
                client=client,
            )
        )

        return providers

    def build_portfolio_sync_service(
        self,
    ) -> PortfolioSyncService:
        return PortfolioSyncService(
            providers=self.build_portfolio_providers()
        )

    def _get_enabled_binance_client(
        self,
    ) -> object | None:
        if not self._settings.enable_binance_execution:
            return None

        if self._binance_client_initialized:
            return self._binance_client

        self._settings.validate_binance_activation()

        client = self._binance_client_factory(
            self._settings
        )

        if client is None:
            raise RuntimeError(
                "Binance integration is enabled, but "
                "the client factory returned no client."
            )

        self._binance_client = client
        self._binance_client_initialized = True

        return client

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


def create_portfolio_sync_service(
    *,
    settings: ExchangeExecutionSettings | None = None,
) -> PortfolioSyncService:
    return ExchangeAdapterRegistry(
        settings=settings
    ).build_portfolio_sync_service()
