from __future__ import annotations

from pydantic import BaseModel, Field


class RuntimeRiskCheckRequest(BaseModel):
    equity: float = Field(gt=0)
    peak_equity: float = Field(gt=0)
    daily_pnl: float
    open_positions: int = Field(ge=0)
    current_exposure_value: float = Field(ge=0)
    correlated_exposure_value: float = Field(
        default=0.0,
        ge=0,
    )

    max_daily_loss_percent: float = Field(
        default=3.0,
        gt=0,
        le=100,
    )
    max_drawdown_percent: float = Field(
        default=10.0,
        gt=0,
        le=100,
    )
    max_total_exposure_percent: float = Field(
        default=80.0,
        gt=0,
        le=100,
    )
    max_correlated_exposure_percent: float = Field(
        default=40.0,
        gt=0,
        le=100,
    )
    max_open_positions: int = Field(
        default=5,
        gt=0,
    )
    minimum_position_value: float = Field(
        default=25.0,
        ge=0,
    )


class RuntimeRiskCheckResponse(BaseModel):
    status: str
    trading_allowed: bool
    daily_loss_percent: float
    drawdown_percent: float
    total_exposure_percent: float
    open_positions: int
    reasons: list[str]
    warnings: list[str]
