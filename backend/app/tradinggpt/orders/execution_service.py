from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from .adapters import (
    ExchangeOrderAdapter,
    PaperOrderAdapter,
)
from .execution_models import OrderExecutionResult
from .models import ExchangeName, OrderIntent


class UnsupportedExchangeError(ValueError):
    """Raised when no execution adapter is registered."""


class OrderExecutionService:
    def __init__(
        self,
        *,
        adapters: list[ExchangeOrderAdapter] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        configured_adapters = adapters or [
            PaperOrderAdapter(),
        ]

        self._adapters = {
            adapter.exchange: adapter
            for adapter in configured_adapters
        }
        self._id_factory = id_factory or self._default_id

    def execute(
        self,
        intent: OrderIntent,
    ) -> OrderExecutionResult:
        adapter = self._adapters.get(intent.exchange)

        if adapter is None:
            raise UnsupportedExchangeError(
                f"No adapter registered for {intent.exchange}."
            )

        return adapter.execute(
            intent=intent,
            client_order_id=self._id_factory(),
        )

    def supports(
        self,
        exchange: ExchangeName,
    ) -> bool:
        return exchange in self._adapters

    @staticmethod
    def _default_id() -> str:
        return uuid4().hex
