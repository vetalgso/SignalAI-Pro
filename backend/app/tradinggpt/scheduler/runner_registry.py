from __future__ import annotations

import threading

from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.core.config import settings

from .distributed_lock import (
    PostgresAdvisorySchedulerLock,
    SchedulerDistributedLock,
)
from .payload_executor import (
    execute_persisted_scheduler_payload,
)
from .runner import SafeSchedulerRunner
from .state_repository import (
    SchedulerStateRepository,
)


_scheduler_execution_lock = threading.Lock()


def _resolve_engine(
    session: Session,
) -> Engine:
    bind = session.get_bind()

    if isinstance(bind, Engine):
        return bind

    if isinstance(bind, Connection):
        return bind.engine

    raise TypeError(
        "Scheduler session must be bound to "
        "a SQLAlchemy Engine or Connection."
    )


def create_scheduler_distributed_lock(
    session: Session,
) -> SchedulerDistributedLock | None:
    if (
        not settings
        .scheduler_distributed_lock_enabled
    ):
        return None

    engine = _resolve_engine(session)

    if engine.dialect.name != "postgresql":
        return None

    return PostgresAdvisorySchedulerLock(
        engine=engine,
        lock_key=(
            settings.scheduler_advisory_lock_key
        ),
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
        execution_lock=(
            _scheduler_execution_lock
        ),
        distributed_lock=(
            create_scheduler_distributed_lock(
                session
            )
        ),
    )
