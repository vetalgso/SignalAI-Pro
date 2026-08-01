from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

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
        if (
            self.market_type == "SPOT"
            and self.leverage != 1
        ):
            raise ValueError(
                "SPOT orders must use leverage=1."
            )

        if (
            self.order_type == "LIMIT"
            and self.reference_price is None
        ):
            raise ValueError(
                "LIMIT orders require reference_price."
            )

        return self


class JournalOrderExecuteRequest(
    OrderExecuteRequest
):
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
    )
    dry_run: bool = False


class OrderExecuteResponse(BaseModel):
    exchange: ExchangeName
    symbol: str
    side: OrderSide
    order_type: OrderType
    status: Literal[
        "FILLED",
        "OPEN",
        "PARTIALLY_FILLED",
        "CANCELED",
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


class OrderJournalResponse(BaseModel):
    journal_id: int
    idempotency_key: str
    replayed: bool = False
    dry_run: bool

    exchange: str
    market_type: str
    symbol: str
    side: str
    order_type: str
    status: str

    requested_quantity: float
    normalized_quantity: float | None
    requested_price: float | None
    normalized_price: float | None
    filled_quantity: float
    average_price: float | None

    client_order_id: str | None
    exchange_order_id: str | None
    simulated: bool

    request_payload: dict[str, Any]
    preview_payload: dict[str, Any] | None
    execution_payload: dict[str, Any] | None
    error_message: str | None

    created_at: datetime
    updated_at: datetime


class SymbolTradingRulesResponse(BaseModel):
    exchange: ExchangeName
    symbol: str
    status: str
    base_asset: str
    quote_asset: str
    min_quantity: float | None = None
    max_quantity: float | None = None
    quantity_step: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    price_tick: float | None = None
    min_notional: float | None = None


class OrderPreviewResponse(BaseModel):
    exchange: ExchangeName
    symbol: str
    side: OrderSide
    order_type: OrderType
    valid: bool
    requested_quantity: float
    normalized_quantity: float
    requested_price: float | None
    normalized_price: float | None
    estimated_notional: float | None
    available_balance: float | None
    balance_asset: str | None
    errors: list[str]
    warnings: list[str]


OrderStatusResponse = OrderExecuteResponse
OrderCancelResponse = OrderExecuteResponse
