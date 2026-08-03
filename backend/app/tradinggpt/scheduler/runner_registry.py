from __future__ import annotations

from sqlalchemy.orm import Session

from .runner import SafeSchedulerRunner
from .state_repository import (
    SchedulerStateRepository,
)


def create_scheduler_runner(
    session: Session,
) -> SafeSchedulerRunner:
    return SafeSchedulerRunner(
        state_repository=(
            SchedulerStateRepository(session)
        ),
        cycle_callback=lambda: None,
    )
