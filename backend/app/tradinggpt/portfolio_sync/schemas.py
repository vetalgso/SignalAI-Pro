from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PortfolioSnapshotRecordResponse(BaseModel):
    id: int
    source: str
    total_wallet_balance: float | None
    balances_count: int
    open_orders_count: int
    positions_count: int
    snapshot_payload: dict[str, Any]
    captured_at: datetime
    created_at: datetime


class EquityPointResponse(BaseModel):
    snapshot_id: int
    equity: float
    captured_at: datetime


class PortfolioAnalyticsResponse(BaseModel):
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
    equity_curve: list[EquityPointResponse]
