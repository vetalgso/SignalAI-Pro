from __future__ import annotations

from typing import Protocol

from ..execution_models import OrderExecutionResult
from ..models import ExchangeName, OrderIntent


class ExchangeOrderAdapter(Protocol):
    @property
    def exchange(self) -> ExchangeName:
        """Exchange handled by this adapter."""

    def execute(
        self,
        *,
        intent: OrderIntent,
        client_order_id: str,
    ) -> OrderExecutionResult:
        """Execute or register an order intent."""
