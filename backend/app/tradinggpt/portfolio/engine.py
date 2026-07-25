from __future__ import annotations

from collections.abc import Mapping

from app.tradinggpt.portfolio.models import (
    PortfolioAction,
    PortfolioPosition,
    PortfolioResult,
    PortfolioRisk,
    RebalanceTrade,
    TradeAction,
)


class PortfolioEngine:
    """
    Deterministic portfolio allocation and risk engine.

    Version 1 responsibilities:
    - build allocation from investor risk profile;
    - enforce maximum position size;
    - preserve exactly 100% total allocation;
    - calculate monetary allocation;
    - calculate portfolio risk score;
    - classify positions as ADD/HOLD/REDUCE/AVOID;
    - define maximum risk per trade.
    """

    CASH_ASSET = "Cash / USD"

    RISK_PER_TRADE = {
        "low": 0.50,
        "medium": 1.00,
        "high": 2.00,
    }

    ASSET_RISK_SCORES = {
        "Cash / USD": 5.0,
        "Gold": 25.0,
        "S&P 500 ETF": 40.0,
        "NASDAQ ETF": 55.0,
        "BTC": 85.0,
        "ETH": 88.0,
        "Growth Stocks": 75.0,
    }

    BASE_ALLOCATIONS = {
        "low": {
            "Cash / USD": 30.0,
            "Gold": 25.0,
            "NASDAQ ETF": 20.0,
            "BTC": 15.0,
            "ETH": 10.0,
        },
        "medium": {
            "BTC": 25.0,
            "ETH": 20.0,
            "NASDAQ ETF": 20.0,
            "Gold": 15.0,
            "S&P 500 ETF": 10.0,
            "Cash / USD": 10.0,
        },
        "high": {
            "BTC": 35.0,
            "ETH": 25.0,
            "NASDAQ ETF": 20.0,
            "Growth Stocks": 10.0,
            "Gold": 5.0,
            "Cash / USD": 5.0,
        },
    }

    REASONS = {
        "Cash / USD": (
            "Резерв ликвидности для снижения риска и новых возможностей."
        ),
        "Gold": (
            "Защитная часть портфеля для снижения общей волатильности."
        ),
        "S&P 500 ETF": (
            "Широкая диверсификация по крупным публичным компаниям."
        ),
        "NASDAQ ETF": (
            "Экспозиция к технологическому сектору и компаниям роста."
        ),
        "BTC": (
            "Основная криптовалютная позиция с повышенным потенциалом "
            "и риском."
        ),
        "ETH": (
            "Диверсификация криптовалютной части портфеля."
        ),
        "Growth Stocks": (
            "Дополнительная экспозиция к высокорисковым активам роста."
        ),
    }

    @classmethod
    def build(
        cls,
        *,
        risk_level: PortfolioRisk,
        capital: float | None = None,
        currency: str = "USD",
        max_position_percent: float = 25.0,
        current_allocations: Mapping[str, float] | None = None,
    ) -> PortfolioResult:
        cls._validate_inputs(
            capital=capital,
            max_position_percent=max_position_percent,
            current_allocations=current_allocations,
        )

        allocation = dict(
            cls.BASE_ALLOCATIONS.get(
                risk_level,
                cls.BASE_ALLOCATIONS["medium"],
            )
        )

        warnings: list[str] = []

        overflow = cls._apply_position_limit(
            allocation,
            max_position_percent,
        )

        if overflow > 0:
            allocation[cls.CASH_ASSET] = (
                allocation.get(cls.CASH_ASSET, 0.0)
                + overflow
            )
            warnings.append(
                "Позиции выше пользовательского лимита были ограничены; "
                "освободившаяся доля переведена в денежный резерв."
            )

        allocation = cls._normalize_allocation(allocation)

        positions = cls._build_positions(
            allocation=allocation,
            capital=capital,
            current_allocations=current_allocations or {},
        )

        trades = cls._build_rebalance_trades(
            allocation=allocation,
            capital=capital,
            currency=currency,
            current_allocations=current_allocations or {},
        )

        portfolio_risk_score = cls._portfolio_risk_score(
            allocation
        )

        cash_reserve_percent = allocation.get(
            cls.CASH_ASSET,
            0.0,
        )
        invested_percent = 100.0 - cash_reserve_percent

        if portfolio_risk_score >= 70:
            warnings.append(
                "Портфель имеет высокую концентрацию волатильных активов."
            )

        if cash_reserve_percent < 5:
            warnings.append(
                "Денежный резерв ниже 5% капитала."
            )

        return PortfolioResult(
            capital=capital,
            currency=currency.upper(),
            risk_level=risk_level,
            max_position_percent=max_position_percent,
            max_risk_per_trade_percent=cls.RISK_PER_TRADE[
                risk_level
            ],
            portfolio_risk_score=portfolio_risk_score,
            cash_reserve_percent=cash_reserve_percent,
            invested_percent=invested_percent,
            positions=positions,
            trades=trades,
            warnings=warnings,
        )

    @classmethod
    def _apply_position_limit(
        cls,
        allocation: dict[str, float],
        max_position_percent: float,
    ) -> float:
        """
        Caps investable assets. Cash is intentionally exempt because
        overflow from risk limits must remain somewhere in the portfolio.
        """
        overflow = 0.0

        for asset, percent in list(allocation.items()):
            if asset == cls.CASH_ASSET:
                continue

            if percent <= max_position_percent:
                continue

            overflow += percent - max_position_percent
            allocation[asset] = max_position_percent

        return overflow

    @staticmethod
    def _normalize_allocation(
        allocation: dict[str, float],
    ) -> dict[str, float]:
        total = sum(allocation.values())

        if total <= 0:
            raise ValueError(
                "Portfolio allocation total must be positive."
            )

        normalized = {
            asset: percent / total * 100.0
            for asset, percent in allocation.items()
        }

        # Correct floating-point residue on the cash position when
        # available, otherwise on the final allocation item.
        residue = 100.0 - sum(normalized.values())
        correction_asset = (
            PortfolioEngine.CASH_ASSET
            if PortfolioEngine.CASH_ASSET in normalized
            else next(reversed(normalized))
        )
        normalized[correction_asset] += residue

        return normalized

    @classmethod
    def _build_positions(
        cls,
        *,
        allocation: Mapping[str, float],
        capital: float | None,
        current_allocations: Mapping[str, float],
    ) -> list[PortfolioPosition]:
        positions: list[PortfolioPosition] = []

        all_assets = list(allocation)

        for asset in current_allocations:
            if asset not in allocation:
                all_assets.append(asset)

        for asset in all_assets:
            target = float(allocation.get(asset, 0.0))
            current = float(current_allocations.get(asset, 0.0))

            action = cls._position_action(
                target_percent=target,
                current_percent=current,
                position_exists=asset in current_allocations,
            )

            amount = (
                round(capital * target / 100.0, 2)
                if capital is not None
                else None
            )

            reason = cls.REASONS.get(
                asset,
                "Актив не входит в базовую целевую структуру портфеля.",
            )

            if action == "REDUCE":
                reason = (
                    f"Текущая доля {current:.2f}% превышает "
                    f"целевую долю {target:.2f}%."
                )
            elif action == "AVOID":
                reason = (
                    "Актив отсутствует в целевой структуре выбранного "
                    "риск-профиля."
                )

            positions.append(
                PortfolioPosition(
                    asset=asset,
                    target_percent=target,
                    amount=amount,
                    action=action,
                    risk_score=cls.ASSET_RISK_SCORES.get(
                        asset,
                        70.0,
                    ),
                    reason=reason,
                )
            )

        return positions

    @classmethod
    def _build_rebalance_trades(
        cls,
        *,
        allocation: Mapping[str, float],
        capital: float | None,
        currency: str,
        current_allocations: Mapping[str, float],
    ) -> list[RebalanceTrade]:
        trades: list[RebalanceTrade] = []
        all_assets = list(allocation)

        for asset in current_allocations:
            if asset not in allocation:
                all_assets.append(asset)

        for asset in all_assets:
            current_percent = float(
                current_allocations.get(asset, 0.0)
            )
            target_percent = float(
                allocation.get(asset, 0.0)
            )
            delta_percent = (
                target_percent - current_percent
            )

            action = cls._trade_action(
                current_percent=current_percent,
                target_percent=target_percent,
                delta_percent=delta_percent,
            )

            current_amount = (
                round(
                    capital * current_percent / 100.0,
                    2,
                )
                if capital is not None
                else None
            )
            target_amount = (
                round(
                    capital * target_percent / 100.0,
                    2,
                )
                if capital is not None
                else None
            )
            trade_amount = (
                round(
                    abs(capital * delta_percent / 100.0),
                    2,
                )
                if capital is not None
                else None
            )

            reason = cls._trade_reason(
                action=action,
                current_percent=current_percent,
                target_percent=target_percent,
                delta_percent=delta_percent,
                currency=currency,
                trade_amount=trade_amount,
            )

            trades.append(
                RebalanceTrade(
                    asset=asset,
                    action=action,
                    current_percent=current_percent,
                    target_percent=target_percent,
                    delta_percent=delta_percent,
                    current_amount=current_amount,
                    target_amount=target_amount,
                    trade_amount=trade_amount,
                    currency=currency.upper(),
                    reason=reason,
                )
            )

        return trades

    @staticmethod
    def _trade_action(
        *,
        current_percent: float,
        target_percent: float,
        delta_percent: float,
    ) -> TradeAction:
        tolerance = max(
            0.01,
            target_percent * 0.001,
        )

        if (
            current_percent > 0
            and target_percent <= tolerance
        ):
            return "EXIT"

        if delta_percent > tolerance:
            return "BUY"

        if delta_percent < -tolerance:
            return "SELL"

        return "HOLD"

    @staticmethod
    def _trade_reason(
        *,
        action: TradeAction,
        current_percent: float,
        target_percent: float,
        delta_percent: float,
        currency: str,
        trade_amount: float | None,
    ) -> str:
        amount_text = (
            f"{trade_amount:,.2f} {currency.upper()}"
            if trade_amount is not None
            else f"{abs(delta_percent):.2f}% портфеля"
        )

        if action == "BUY":
            return (
                f"Увеличить позицию с "
                f"{current_percent:.2f}% до "
                f"{target_percent:.2f}%: купить на "
                f"{amount_text}."
            )

        if action == "SELL":
            return (
                f"Сократить позицию с "
                f"{current_percent:.2f}% до "
                f"{target_percent:.2f}%: продать на "
                f"{amount_text}."
            )

        if action == "EXIT":
            return (
                f"Закрыть позицию полностью: продать на "
                f"{amount_text}."
            )

        return (
            f"Сохранить позицию около "
            f"{target_percent:.2f}% без операции."
        )

    @staticmethod
    def _position_action(
        *,
        target_percent: float,
        current_percent: float,
        position_exists: bool,
    ) -> PortfolioAction:
        if target_percent <= 0:
            return "AVOID"

        if not position_exists:
            return "ADD"

        tolerance = max(1.0, target_percent * 0.10)

        if current_percent > target_percent + tolerance:
            return "REDUCE"

        if current_percent < target_percent - tolerance:
            return "ADD"

        return "HOLD"

    @classmethod
    def _portfolio_risk_score(
        cls,
        allocation: Mapping[str, float],
    ) -> float:
        weighted_risk = sum(
            percent
            * cls.ASSET_RISK_SCORES.get(asset, 70.0)
            for asset, percent in allocation.items()
        ) / 100.0

        return round(
            max(0.0, min(100.0, weighted_risk)),
            2,
        )

    @staticmethod
    def _validate_inputs(
        *,
        capital: float | None,
        max_position_percent: float,
        current_allocations: Mapping[str, float] | None,
    ) -> None:
        if capital is not None and capital <= 0:
            raise ValueError(
                "Capital must be greater than zero."
            )

        if not 0 < max_position_percent <= 100:
            raise ValueError(
                "Maximum position percent must be between 0 and 100."
            )

        if current_allocations is None:
            return

        for asset, percent in current_allocations.items():
            if not asset:
                raise ValueError(
                    "Current allocation asset name cannot be empty."
                )

            if percent < 0 or percent > 100:
                raise ValueError(
                    "Current allocation percent must be between "
                    "0 and 100."
                )

        current_total = sum(current_allocations.values())

        if current_total > 100.000001:
            raise ValueError(
                "Current allocations cannot exceed 100%."
            )
