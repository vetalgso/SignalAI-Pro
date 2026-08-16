from __future__ import annotations

from dataclasses import (
    dataclass,
    replace,
)

from .validation_models import (
    OrderPreviewResult,
)


@dataclass(frozen=True, slots=True)
class OrderRiskPolicy:
    execution_enabled: bool = True
    max_order_notional: float | None = None
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
            allowed_symbols=(
                normalized_symbols
            ),
        )

    def apply(
        self,
        preview: OrderPreviewResult,
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

        if self.max_order_notional is not None:
            notional = (
                preview.estimated_notional
            )

            if notional is None:
                errors.append(
                    "Order notional could not be "
                    "estimated; execution is blocked."
                )
            elif (
                notional
                > self.max_order_notional
            ):
                errors.append(
                    "Order notional "
                    f"{notional:.8f} exceeds "
                    "TESTNET risk limit "
                    f"{self.max_order_notional:.8f}."
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
