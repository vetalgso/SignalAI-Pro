from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from app.models.portfolio_snapshot import (
    PortfolioSnapshotRecord,
)


@dataclass(frozen=True, slots=True)
class EquityPoint:
    snapshot_id: int
    equity: float
    captured_at: datetime

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PortfolioAnalytics:
    source: str
    snapshots_count: int
    current_equity: float | None
    initial_equity: float | None
    peak_equity: float | None
    minimum_equity: float | None
    equity_change: float | None
    equity_change_percent: float | None
    current_drawdown: float | None
    current_drawdown_percent: float | None
    max_drawdown: float | None
    max_drawdown_percent: float | None
    equity_curve: tuple[EquityPoint, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["equity_curve"] = [
            point.to_dict()
            for point in self.equity_curve
        ]
        return payload


class PortfolioAnalyticsService:
    def calculate(
        self,
        *,
        source: str,
        records: list[
            PortfolioSnapshotRecord
        ],
    ) -> PortfolioAnalytics:
        points = tuple(
            EquityPoint(
                snapshot_id=record.id,
                equity=float(
                    record.total_wallet_balance
                ),
                captured_at=record.captured_at,
            )
            for record in records
            if record.total_wallet_balance
            is not None
        )

        if not points:
            return PortfolioAnalytics(
                source=source.upper(),
                snapshots_count=len(records),
                current_equity=None,
                initial_equity=None,
                peak_equity=None,
                minimum_equity=None,
                equity_change=None,
                equity_change_percent=None,
                current_drawdown=None,
                current_drawdown_percent=None,
                max_drawdown=None,
                max_drawdown_percent=None,
                equity_curve=(),
            )

        equities = [
            point.equity for point in points
        ]

        initial = equities[0]
        current = equities[-1]
        peak = max(equities)
        minimum = min(equities)

        change = current - initial
        change_percent = (
            change / initial * 100
            if initial != 0
            else None
        )

        current_drawdown = peak - current
        current_drawdown_percent = (
            current_drawdown / peak * 100
            if peak != 0
            else None
        )

        running_peak = equities[0]
        max_drawdown = 0.0
        max_drawdown_percent = 0.0

        for equity in equities:
            running_peak = max(
                running_peak,
                equity,
            )
            drawdown = running_peak - equity
            drawdown_percent = (
                drawdown / running_peak * 100
                if running_peak != 0
                else 0.0
            )

            max_drawdown = max(
                max_drawdown,
                drawdown,
            )
            max_drawdown_percent = max(
                max_drawdown_percent,
                drawdown_percent,
            )

        return PortfolioAnalytics(
            source=source.upper(),
            snapshots_count=len(records),
            current_equity=round(current, 8),
            initial_equity=round(initial, 8),
            peak_equity=round(peak, 8),
            minimum_equity=round(minimum, 8),
            equity_change=round(change, 8),
            equity_change_percent=(
                round(change_percent, 8)
                if change_percent is not None
                else None
            ),
            current_drawdown=round(
                current_drawdown,
                8,
            ),
            current_drawdown_percent=(
                round(
                    current_drawdown_percent,
                    8,
                )
                if current_drawdown_percent
                is not None
                else None
            ),
            max_drawdown=round(
                max_drawdown,
                8,
            ),
            max_drawdown_percent=round(
                max_drawdown_percent,
                8,
            ),
            equity_curve=points,
        )
