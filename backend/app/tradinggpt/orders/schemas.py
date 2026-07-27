from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .models import (
    ExchangeMarketType,
    ExchangeName,
    OrderSide,
    OrderType,
)


class OrderExecuteRequest(BaseModel):
    exchange: ExchangeName = "PAPER"
    market_type: ExchangeMarketType = "SPOT"

    symbol: str = Field(min_length=1)

    side: OrderSide
    order_type: OrderType

    quantity: float = Field(gt=0)

    reference_price: float | None = Field(
        default=None,
        gt=0,
    )

    stop_loss: float | None = Field(
        default=None,
        gt=0,
    )
    take_profit_1: float | None = Field(
        default=None,
        gt=0,
    )
    take_profit_2: float | None = Field(
        default=None,
        gt=0,
    )

    leverage: int = Field(default=1, ge=1)
    reduce_only: bool = False

    @model_validator(mode="after")
    def validate_market_configuration(
        self,
    ) -> "OrderExecuteRequest":
        if self.market_type == "SPOT" and self.leverage != 1:
            raise ValueError(
                "SPOT orders must use leverage=1."
            )

        return self


class OrderExecuteResponse(BaseModel):
    exchange: ExchangeName
    symbol: str
    side: OrderSide
    order_type: OrderType

    status: Literal[
        "FILLED",
        "OPEN",
        "REJECTED",
        "FAILED",
    ]

    client_order_id: str
    exchange_order_id: str | None

    requested_quantity: float
    filled_quantity: float
    average_price: float | None

    simulated: bool
    message: str
