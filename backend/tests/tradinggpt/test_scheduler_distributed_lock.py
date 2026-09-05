from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from app.tradinggpt.scheduler.distributed_lock import (
    PostgresAdvisorySchedulerLock,
)


def test_postgres_lock_rejects_sqlite_engine() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    with pytest.raises(
        ValueError,
        match="requires a PostgreSQL engine",
    ):
        PostgresAdvisorySchedulerLock(
            engine=engine,
            lock_key=2026080320,
        )
