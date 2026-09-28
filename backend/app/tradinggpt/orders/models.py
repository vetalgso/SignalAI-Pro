from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


ExchangeName = Literal[
    "PAPER",
    "BINANCE",
    "BYBIT",
    "OKX",
]

ExchangeMarketType = Literal[
    "SPOT",
    "FUTURES",
]

OrderSide = Literal[
    "BUY",
    "SELL",
]

OrderType = Literal[
    "MARKET",
    "LIMIT",
]


@dataclass(frozen=True, slots=True)
class OrderRoutingContext:
    exchange: ExchangeName = "PAPER"
    market_type: ExchangeMarketType = "SPOT"
    order_type: OrderType = "MARKET"
    leverage: int = 1


@dataclass(frozen=True, slots=True)
class OrderIntent:
    exchange: ExchangeName
    market_type: ExchangeMarketType

    symbol: str
    side: OrderSide
    order_type: OrderType

    quantity: float
    reference_price: float | None

    stop_loss: float | None
    take_profit_1: float | None
    take_profit_2: float | None

    leverage: int = 1
    reduce_only: bool = False

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)

        payload["quantity"] = round(self.quantity, 8)
        payload["reference_price"] = self._round_optional(
            self.reference_price,
        )
        payload["stop_loss"] = self._round_optional(
            self.stop_loss,
        )
        payload["take_profit_1"] = self._round_optional(
            self.take_profit_1,
        )
        payload["take_profit_2"] = self._round_optional(
            self.take_profit_2,
        )

        return payload

    @staticmethod
    def _round_optional(
        value: float | None,
    ) -> float | None:
        if value is None:
            return None

        return round(value, 8)
