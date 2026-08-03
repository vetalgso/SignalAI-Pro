from __future__ import annotations

from sqlalchemy.orm import Session

from .payload_executor import (
    execute_persisted_scheduler_payload,
)
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
        cycle_callback=lambda: (
            execute_persisted_scheduler_payload(
                session
            )
        ),
    )
