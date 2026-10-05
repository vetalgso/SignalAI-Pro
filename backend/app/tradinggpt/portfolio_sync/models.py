from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PortfolioSource = Literal[
    "PAPER",
    "BINANCE",
]


class AssetBalance(BaseModel):
    """Normalized balance of one exchange asset."""

    model_config = ConfigDict(frozen=True)

    asset: str = Field(min_length=1)
    free: float = Field(ge=0.0)
    locked: float = Field(ge=0.0)

    @property
    def total(self) -> float:
        return self.free + self.locked


class OpenOrder(BaseModel):
    """Normalized open exchange order."""

    model_config = ConfigDict(frozen=True)

    exchange_order_id: str
    client_order_id: str | None = None
    symbol: str
    side: Literal["BUY", "SELL"]
    order_type: str
    status: str
    price: float = Field(ge=0.0)
    original_quantity: float = Field(ge=0.0)
    executed_quantity: float = Field(ge=0.0)


class ExchangePosition(BaseModel):
    """Position derived from synchronized exchange balances."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    quantity: float
    entry_price: float | None = Field(
        default=None,
        ge=0.0,
    )
    unrealized_pnl: float = 0.0


class PortfolioSnapshot(BaseModel):
    """Read-only snapshot of an exchange portfolio."""

    model_config = ConfigDict(frozen=True)

    source: PortfolioSource
    balances: list[AssetBalance] = Field(
        default_factory=list
    )
    open_orders: list[OpenOrder] = Field(
        default_factory=list
    )
    positions: list[ExchangePosition] = Field(
        default_factory=list
    )
    total_wallet_balance: float | None = Field(
        default=None,
        ge=0.0,
    )
    captured_at: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )
