from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from .models import ExchangeName, OrderSide, OrderType


OrderExecutionStatus = Literal[
    "FILLED",
    "OPEN",
    "PARTIALLY_FILLED",
    "CANCELED",
    "REJECTED",
    "FAILED",
]


@dataclass(frozen=True, slots=True)
class OrderExecutionResult:
    exchange: ExchangeName
    symbol: str
    side: OrderSide
    order_type: OrderType
    status: OrderExecutionStatus
    client_order_id: str
    exchange_order_id: str | None
    requested_quantity: float
    filled_quantity: float
    average_price: float | None
    simulated: bool
    message: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["requested_quantity"] = round(self.requested_quantity, 8)
        payload["filled_quantity"] = round(self.filled_quantity, 8)
        if self.average_price is not None:
            payload["average_price"] = round(self.average_price, 8)
        return payload
