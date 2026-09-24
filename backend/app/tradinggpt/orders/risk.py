from __future__ import annotations

from collections.abc import Sequence
from dataclasses import (
    dataclass,
    replace,
)

from .execution_models import (
    OrderExecutionResult,
)
from .validation_models import (
    OrderPreviewResult,
)


class OrderRiskUsageUnavailableError(
    RuntimeError
):
    pass


def count_verified_open_orders(
    results: Sequence[
        OrderExecutionResult
    ],
) -> int:
    allowed_statuses = {
        "OPEN",
        "PARTIALLY_FILLED",
    }

    if any(
        result.status not in allowed_statuses
        for result in results
    ):
        raise OrderRiskUsageUnavailableError(
            "Binance TESTNET open-order "
            "usage could not be verified."
        )

    return len(results)


@dataclass(frozen=True, slots=True)
class OrderRiskUsage:
    daily_notional: float = 0.0
    open_orders: int = 0


@dataclass(frozen=True, slots=True)
class OrderRiskPolicy:
    execution_enabled: bool = True
    max_order_notional: float | None = None
    max_daily_notional: float | None = None
    max_open_orders: int | None = None
    allowed_symbols: frozenset[str] = (
        frozenset()
    )

    @classmethod
    def configured(
        cls,
        *,
        execution_enabled: bool,
        max_order_notional: float,
        allowed_symbols: str,
        max_daily_notional: (
            float | None
        ) = None,
        max_open_orders: int | None = None,
    ) -> "OrderRiskPolicy":
        normalized_symbols = frozenset(
            symbol.strip().upper()
            for symbol in (
                allowed_symbols.split(",")
            )
            if symbol.strip()
        )

        return cls(
            execution_enabled=(
                execution_enabled
            ),
            max_order_notional=(
                max_order_notional
            ),
            max_daily_notional=(
                max_daily_notional
            ),
            max_open_orders=max_open_orders,
            allowed_symbols=(
                normalized_symbols
            ),
        )

    @property
    def requires_account_usage(
        self,
    ) -> bool:
        return (
            self.max_daily_notional is not None
            or self.max_open_orders is not None
        )

    @property
    def requires_open_order_usage(
        self,
    ) -> bool:
        return self.max_open_orders is not None

    def apply(
        self,
        preview: OrderPreviewResult,
        *,
        usage: OrderRiskUsage | None = None,
        increases_exposure: bool = True,
    ) -> OrderPreviewResult:
        if not preview.valid:
            return preview

        errors: list[str] = []

        if not self.execution_enabled:
            errors.append(
                "TESTNET order execution is "
                "disabled by risk policy."
            )

        symbol = preview.symbol.upper()

        if (
            self.allowed_symbols
            and symbol
            not in self.allowed_symbols
        ):
            errors.append(
                f"Symbol {symbol} is not allowed "
                "by TESTNET risk policy."
            )

        current_usage = (
            usage or OrderRiskUsage()
        )
        notional = preview.estimated_notional

        notional_required = (
            self.max_order_notional is not None
            or (
                increases_exposure
                and self.max_daily_notional
                is not None
            )
        )

        if (
            notional_required
            and notional is None
        ):
            errors.append(
                "Order notional could not be "
                "estimated; execution is blocked."
            )
        elif notional is not None:
            if (
                self.max_order_notional
                is not None
                and notional
                > self.max_order_notional
            ):
                errors.append(
                    "Order notional "
                    f"{notional:.8f} exceeds "
                    "TESTNET risk limit "
                    f"{self.max_order_notional:.8f}."
                )

            projected_daily_notional = (
                current_usage.daily_notional
                + notional
            )

            if (
                increases_exposure
                and self.max_daily_notional
                is not None
                and projected_daily_notional
                > self.max_daily_notional
            ):
                errors.append(
                    "Projected daily notional "
                    f"{projected_daily_notional:.8f} "
                    "exceeds TESTNET daily limit "
                    f"{self.max_daily_notional:.8f}."
                )

        if (
            increases_exposure
            and self.max_open_orders is not None
            and current_usage.open_orders
            >= self.max_open_orders
        ):
            errors.append(
                "Open order count "
                f"{current_usage.open_orders} reached "
                "TESTNET limit "
                f"{self.max_open_orders}."
            )

        if not errors:
            return preview

        return replace(
            preview,
            valid=False,
            errors=[
                *preview.errors,
                *errors,
            ],
        )
