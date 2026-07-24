from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SignalCreate(BaseModel):
    symbol: str = Field(min_length=3, max_length=20, examples=["BTCUSDT"])
    timeframe: str = Field(min_length=2, max_length=10, examples=["1h"])
    strategy: str = Field(min_length=2, max_length=80, examples=["ema_cross"])
    side: Literal["LONG", "SHORT"]
    entry_price: Decimal = Field(gt=0)
    stop_loss: Decimal = Field(gt=0)
    take_profit: Decimal = Field(gt=0)
    confidence: Decimal = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_trade_levels(self) -> "SignalCreate":
        if self.side == "LONG" and not (
            self.stop_loss < self.entry_price < self.take_profit
        ):
            raise ValueError("LONG requires stop_loss < entry_price < take_profit")
        if self.side == "SHORT" and not (
            self.take_profit < self.entry_price < self.stop_loss
        ):
            raise ValueError("SHORT requires take_profit < entry_price < stop_loss")
        return self


class SignalRead(SignalCreate):
    id: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
