from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from .adapters import ExchangeOrderAdapter, PaperOrderAdapter
from .execution_models import OrderExecutionResult
from .models import ExchangeName, OrderIntent
from .validation_models import OrderPreviewResult, SymbolTradingRules


class UnsupportedExchangeError(ValueError):
    """Raised when no execution adapter is registered."""


class UnsupportedOrderOperationError(ValueError):
    """Raised when an adapter does not support an order operation."""


class OrderExecutionService:
    def __init__(self, *, adapters: list[ExchangeOrderAdapter] | None = None, id_factory: Callable[[], str] | None = None) -> None:
        configured_adapters = adapters or [PaperOrderAdapter()]
        self._adapters = {adapter.exchange: adapter for adapter in configured_adapters}
        self._id_factory = id_factory or self._default_id

    def execute(self, intent: OrderIntent) -> OrderExecutionResult:
        adapter = self._get_adapter(intent.exchange)
        return adapter.execute(intent=intent, client_order_id=self._id_factory())

    def get_order(self, *, exchange: ExchangeName, symbol: str, order_id: str) -> OrderExecutionResult:
        return self._call(exchange, "get_order", symbol=symbol, order_id=order_id)

    def cancel_order(self, *, exchange: ExchangeName, symbol: str, order_id: str) -> OrderExecutionResult:
        return self._call(exchange, "cancel_order", symbol=symbol, order_id=order_id)

    def list_open_orders(self, *, exchange: ExchangeName, symbol: str | None = None) -> list[OrderExecutionResult]:
        return self._call(exchange, "list_open_orders", symbol=symbol)

    def get_symbol_rules(self, *, exchange: ExchangeName, symbol: str) -> SymbolTradingRules:
        return self._call(exchange, "get_symbol_rules", symbol=symbol)

    def preview(self, intent: OrderIntent) -> OrderPreviewResult:
        return self._call(intent.exchange, "preview", intent=intent)

    def supports(self, exchange: ExchangeName) -> bool:
        return exchange in self._adapters

    def _call(self, exchange: ExchangeName, operation_name: str, **kwargs: object):
        adapter = self._get_adapter(exchange)
        operation = getattr(adapter, operation_name, None)
        if operation is None:
            raise UnsupportedOrderOperationError(
                f"{operation_name.replace('_', ' ').title()} is not supported for {exchange}."
            )
        return operation(**kwargs)

    def _get_adapter(self, exchange: ExchangeName) -> ExchangeOrderAdapter:
        adapter = self._adapters.get(exchange)
        if adapter is None:
            raise UnsupportedExchangeError(f"No adapter registered for {exchange}.")
        return adapter

    @staticmethod
    def _default_id() -> str:
        return uuid4().hex
