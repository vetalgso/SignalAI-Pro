from __future__ import annotations

from app.core.config import settings
from app.database.session import SessionLocal

from .background_loop import (
    SchedulerBackgroundLoop,
)
from .runner_registry import (
    create_scheduler_runner,
)


def run_scheduler_background_tick(
) -> dict[str, object]:
    with SessionLocal() as session:
        runner = create_scheduler_runner(
            session
        )

        return runner.tick(force=False)


scheduler_background_loop = (
    SchedulerBackgroundLoop(
        tick_callback=(
            run_scheduler_background_tick
        ),
        poll_interval_seconds=(
            settings
            .scheduler_background_poll_seconds
        ),
    )
)
