from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .models import ExchangeName, OrderSide, OrderType


@dataclass(frozen=True, slots=True)
class SymbolTradingRules:
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

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class OrderPreviewResult:
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
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
