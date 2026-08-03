from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


PositionSide = Literal["LONG", "SHORT"]
PositionStatus = Literal[
    "OPEN",
    "PARTIALLY_CLOSED",
    "CLOSED",
]


class PositionCreateRequest(BaseModel):
    exchange: str = Field(
        default="PAPER",
        min_length=1,
        max_length=24,
    )
    market_type: str = Field(
        default="SPOT",
        min_length=1,
        max_length=24,
    )
    symbol: str = Field(
        min_length=1,
        max_length=32,
    )
    side: PositionSide
    quantity: float = Field(gt=0)
    entry_price: float = Field(gt=0)

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

    journal_order_id: int | None = Field(
        default=None,
        ge=1,
    )
    tp1_close_percent: float = Field(
        default=50.0,
        gt=0,
        le=100,
    )
    metadata_payload: dict[str, Any] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_levels(
        self,
    ) -> "PositionCreateRequest":
        if self.side == "LONG":
            if (
                self.stop_loss is not None
                and self.stop_loss >= self.entry_price
            ):
                raise ValueError(
                    "LONG stop_loss must be below entry_price."
                )

            if (
                self.take_profit_1 is not None
                and self.take_profit_1 <= self.entry_price
            ):
                raise ValueError(
                    "LONG take_profit_1 must be above "
                    "entry_price."
                )

            if (
                self.take_profit_2 is not None
                and self.take_profit_2 <= self.entry_price
            ):
                raise ValueError(
                    "LONG take_profit_2 must be above "
                    "entry_price."
                )

        if self.side == "SHORT":
            if (
                self.stop_loss is not None
                and self.stop_loss <= self.entry_price
            ):
                raise ValueError(
                    "SHORT stop_loss must be above "
                    "entry_price."
                )

            if (
                self.take_profit_1 is not None
                and self.take_profit_1 >= self.entry_price
            ):
                raise ValueError(
                    "SHORT take_profit_1 must be below "
                    "entry_price."
                )

            if (
                self.take_profit_2 is not None
                and self.take_profit_2 >= self.entry_price
            ):
                raise ValueError(
                    "SHORT take_profit_2 must be below "
                    "entry_price."
                )

        if (
            self.take_profit_1 is not None
            and self.take_profit_2 is not None
        ):
            if (
                self.side == "LONG"
                and self.take_profit_2
                <= self.take_profit_1
            ):
                raise ValueError(
                    "LONG take_profit_2 must be above "
                    "take_profit_1."
                )

            if (
                self.side == "SHORT"
                and self.take_profit_2
                >= self.take_profit_1
            ):
                raise ValueError(
                    "SHORT take_profit_2 must be below "
                    "take_profit_1."
                )

        return self


class PositionPriceUpdateRequest(BaseModel):
    current_price: float = Field(gt=0)


class PositionCloseRequest(BaseModel):
    exit_price: float = Field(gt=0)


class PositionResponse(BaseModel):
    id: int
    journal_order_id: int | None

    exchange: str
    market_type: str
    symbol: str
    side: PositionSide
    status: PositionStatus

    initial_quantity: float
    remaining_quantity: float
    closed_quantity: float

    entry_price: float
    current_price: float
    exit_price: float | None

    stop_loss: float | None
    take_profit_1: float | None
    take_profit_2: float | None

    tp1_triggered: bool
    tp2_triggered: bool
    break_even_activated: bool
    stop_loss_triggered: bool

    realized_pnl: float
    unrealized_pnl: float

    metadata_payload: dict[str, Any]

    opened_at: datetime
    updated_at: datetime
    closed_at: datetime | None

    actions: list[str] = Field(
        default_factory=list
    )


class PositionMonitorRequest(BaseModel):
    prices: dict[str, float] = Field(
        min_length=1
    )
    exchange: str | None = Field(
        default=None,
        min_length=1,
        max_length=24,
    )


class PositionMonitorResponse(BaseModel):
    checked_positions: int
    updated_positions: int
    missing_symbols: list[str]
    results: list[PositionResponse]


class PositionEventResponse(BaseModel):
    id: int
    position_id: int
    event_type: str
    price: float | None
    payload: dict[str, Any]
    created_at: datetime
