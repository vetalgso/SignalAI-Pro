from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)

from app.tradinggpt.engine.schemas import (
    TradingGPTAnalyzeAndExecuteRequest,
)


class SchedulerRuntimeRiskRequest(BaseModel):
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


class SafeSchedulerCycleRequest(BaseModel):
    runtime_risk: SchedulerRuntimeRiskRequest
    analysis: TradingGPTAnalyzeAndExecuteRequest

    @model_validator(mode="after")
    def enforce_dry_run(
        self,
    ) -> "SafeSchedulerCycleRequest":
        if not self.analysis.dry_run:
            raise ValueError(
                "Safe scheduler cycle requires "
                "analysis.dry_run=true."
            )

        return self


class SafeSchedulerCycleResponse(BaseModel):
    status: str
    dry_run: bool
    risk: dict[str, Any]
    execution: dict[str, Any] | None
    reason: str | None
    cycle_id: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class SchedulerStateUpdateRequest(BaseModel):
    enabled: bool | None = None
    interval_seconds: int | None = Field(
        default=None,
        ge=60,
        le=86400,
    )

    @model_validator(mode="after")
    def require_change(
        self,
    ) -> "SchedulerStateUpdateRequest":
        if (
            self.enabled is None
            and self.interval_seconds is None
        ):
            raise ValueError(
                "At least one scheduler state "
                "field must be provided."
            )

        return self


class SchedulerStateResponse(BaseModel):
    enabled: bool
    interval_seconds: int
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_cycle_id: int | None
    consecutive_failures: int
    updated_at: datetime
