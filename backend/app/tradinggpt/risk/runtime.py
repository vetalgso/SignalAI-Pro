from __future__ import annotations

from dataclasses import asdict, dataclass

from .models import (
    AccountRiskContext,
    RiskLimits,
)


@dataclass(frozen=True, slots=True)
class RuntimeRiskDecision:
    status: str
    trading_allowed: bool
    daily_loss_percent: float
    drawdown_percent: float
    total_exposure_percent: float
    open_positions: int
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class RuntimeRiskGuard:
    @classmethod
    def evaluate(
        cls,
        *,
        account: AccountRiskContext,
        limits: RiskLimits | None = None,
    ) -> RuntimeRiskDecision:
        resolved_limits = limits or RiskLimits()

        cls._validate_account(account)
        cls._validate_limits(resolved_limits)

        daily_loss_percent = cls._percent(
            max(-account.daily_pnl, 0.0),
            account.equity,
        )
        drawdown_percent = cls._percent(
            max(
                account.peak_equity
                - account.equity,
                0.0,
            ),
            account.peak_equity,
        )
        exposure_percent = cls._percent(
            account.current_exposure_value,
            account.equity,
        )

        reasons: list[str] = []
        warnings: list[str] = []

        if (
            daily_loss_percent
            >= resolved_limits.max_daily_loss_percent
        ):
            reasons.append(
                "Maximum daily loss limit has been reached."
            )

        if (
            drawdown_percent
            >= resolved_limits.max_drawdown_percent
        ):
            reasons.append(
                "Maximum account drawdown limit has been reached."
            )

        if (
            account.open_positions
            >= resolved_limits.max_open_positions
        ):
            reasons.append(
                "Maximum number of open positions has been reached."
            )

        if (
            exposure_percent
            >= resolved_limits.max_total_exposure_percent
        ):
            reasons.append(
                "Maximum total exposure limit has been reached."
            )

        correlated_percent = cls._percent(
            account.correlated_exposure_value,
            account.equity,
        )

        if (
            correlated_percent
            >= resolved_limits
            .max_correlated_exposure_percent
        ):
            reasons.append(
                "Maximum correlated exposure limit has been reached."
            )

        if not reasons:
            cls._add_warning(
                warnings=warnings,
                current=daily_loss_percent,
                maximum=(
                    resolved_limits
                    .max_daily_loss_percent
                ),
                label="Daily loss",
            )
            cls._add_warning(
                warnings=warnings,
                current=drawdown_percent,
                maximum=(
                    resolved_limits
                    .max_drawdown_percent
                ),
                label="Account drawdown",
            )
            cls._add_warning(
                warnings=warnings,
                current=exposure_percent,
                maximum=(
                    resolved_limits
                    .max_total_exposure_percent
                ),
                label="Total exposure",
            )

        allowed = not reasons

        return RuntimeRiskDecision(
            status=(
                "ALLOW"
                if allowed
                else "DENY"
            ),
            trading_allowed=allowed,
            daily_loss_percent=daily_loss_percent,
            drawdown_percent=drawdown_percent,
            total_exposure_percent=(
                exposure_percent
            ),
            open_positions=account.open_positions,
            reasons=tuple(
                reasons
                or [
                    "Runtime account risk checks passed."
                ]
            ),
            warnings=tuple(warnings),
        )

    @staticmethod
    def _add_warning(
        *,
        warnings: list[str],
        current: float,
        maximum: float,
        label: str,
    ) -> None:
        if maximum <= 0:
            return

        utilization = current / maximum

        if utilization >= 0.8:
            warnings.append(
                f"{label} is above 80% of its limit."
            )

    @staticmethod
    def _percent(
        value: float,
        base: float,
    ) -> float:
        if base <= 0:
            return 0.0

        return round(
            value / base * 100.0,
            6,
        )

    @staticmethod
    def _validate_account(
        account: AccountRiskContext,
    ) -> None:
        if account.equity <= 0:
            raise ValueError(
                "Account equity must be positive."
            )

        if account.peak_equity <= 0:
            raise ValueError(
                "Peak account equity must be positive."
            )

        if account.open_positions < 0:
            raise ValueError(
                "Open position count cannot be negative."
            )

        if account.current_exposure_value < 0:
            raise ValueError(
                "Current exposure cannot be negative."
            )

        if account.correlated_exposure_value < 0:
            raise ValueError(
                "Correlated exposure cannot be negative."
            )

    @staticmethod
    def _validate_limits(
        limits: RiskLimits,
    ) -> None:
        percentage_values = (
            limits.max_daily_loss_percent,
            limits.max_drawdown_percent,
            limits.max_total_exposure_percent,
            limits.max_correlated_exposure_percent,
        )

        if any(
            value <= 0 or value > 100
            for value in percentage_values
        ):
            raise ValueError(
                "Risk percentage limits must be "
                "between 0 and 100."
            )

        if limits.max_open_positions <= 0:
            raise ValueError(
                "Maximum open positions must be positive."
            )
