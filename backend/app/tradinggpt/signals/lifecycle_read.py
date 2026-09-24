from datetime import datetime, timezone
import math
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models.signal_lifecycle_cycle import SignalLifecycleCycle


router = APIRouter()
FinishedStatus = Literal["COMPLETED", "PARTIAL", "FAILED", "CANCELLED"]


class LifecycleState(BaseModel):
    as_of: datetime
    enabled: bool
    poll_interval_seconds: float
    stale_after_seconds: float
    state: Literal["DISABLED", "WAITING", "STALE", "ERRORS", "UNKNOWN", "OK"]
    completed_at: datetime | None = None
    age_seconds: float | None = None
    duration_seconds: float | None = None
    error_count: int | None = None
    checked_signals: int | None = None
    cycle_status: FinishedStatus | None = None


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def count(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def read_lifecycle_state(
    db: Session, *, enabled: bool, interval_seconds: float, now: datetime,
) -> LifecycleState:
    now = aware(now)
    result = LifecycleState(
        as_of=now, enabled=enabled, poll_interval_seconds=interval_seconds,
        stale_after_seconds=max(3 * interval_seconds, 180),
        state="WAITING" if enabled else "DISABLED",
    )
    with db.no_autoflush:
        cycle = db.scalar(
            select(SignalLifecycleCycle)
            .where(
                SignalLifecycleCycle.completed_at.is_not(None),
                SignalLifecycleCycle.status.in_(("COMPLETED", "PARTIAL", "FAILED", "CANCELLED")),
            )
            .order_by(SignalLifecycleCycle.completed_at.desc(), SignalLifecycleCycle.id.desc())
            .limit(1)
        )
    if cycle is None:
        return result
    result.completed_at = aware(cycle.completed_at)
    result.age_seconds = max(0.0, (now - result.completed_at).total_seconds())
    duration = cycle.duration_seconds
    result.duration_seconds = duration if duration is not None and math.isfinite(duration) and duration >= 0 else None
    result.error_count = count(cycle.error_count)
    result.checked_signals = count(cycle.checked_signals)
    result.cycle_status = cycle.status
    if not enabled:
        return result
    if result.age_seconds > result.stale_after_seconds:
        result.state = "STALE"
    elif cycle.status != "COMPLETED" or (result.error_count or 0) > 0:
        result.state = "ERRORS"
    elif result.error_count is None:
        result.state = "UNKNOWN"
    else:
        result.state = "OK"
    return result


@router.get("/runtime/lifecycle", response_model=LifecycleState)
def get_lifecycle_state(db: Session = Depends(get_db)) -> LifecycleState:
    return read_lifecycle_state(
        db, enabled=settings.signal_tracking_enabled,
        interval_seconds=settings.signal_tracking_interval_seconds,
        now=datetime.now(timezone.utc),
    )
