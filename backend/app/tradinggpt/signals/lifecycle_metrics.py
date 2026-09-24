from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.signal_lifecycle_cycle import SignalLifecycleCycle


def render_lifecycle_metrics(
    session: Session, *, enabled: bool, interval_seconds: float, now: datetime,
) -> list[str]:
    """Read persisted completion state. Never run tracking or expose row labels."""
    cycle = session.scalar(
        select(SignalLifecycleCycle)
        .where(
            SignalLifecycleCycle.completed_at.is_not(None),
            SignalLifecycleCycle.status.in_(("COMPLETED", "PARTIAL", "FAILED", "CANCELLED")),
        )
        .order_by(SignalLifecycleCycle.completed_at.desc(), SignalLifecycleCycle.id.desc())
        .limit(1)
    )
    values = [
        ("enabled", "Whether lifecycle tracking is configured enabled; not worker liveness.", int(enabled)),
        ("poll_interval_seconds", "Configured delay after lifecycle processing in seconds.", interval_seconds),
        ("latest_completed_observed", "Whether a finished lifecycle cycle exists in the journal.", int(cycle is not None)),
    ]
    if cycle is not None:
        completed = cycle.completed_at
        if completed.tzinfo is None:
            completed = completed.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        values.append((
            "seconds_since_last_completion", "Age of latest persisted finished cycle, including failed cycles.",
            max(0.0, (now - completed).total_seconds()),
        ))
        if cycle.duration_seconds is not None:
            values.append(("latest_duration_seconds", "Duration of latest finished lifecycle cycle.", cycle.duration_seconds))
        if cycle.error_count is not None:
            values.append(("latest_errors", "Errors in latest finished cycle; snapshot, not counter.", cycle.error_count))
    lines = []
    for suffix, help_text, value in values:
        name = "signalai_signal_lifecycle_" + suffix
        lines.extend((f"# HELP {name} {help_text}", f"# TYPE {name} gauge", f"{name} {value}"))
    return lines
