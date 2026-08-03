from __future__ import annotations

from typing import Protocol

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


class SchedulerDistributedLock(Protocol):
    def try_acquire(self) -> bool:
        """Try to acquire the distributed lock."""

    def release(self) -> None:
        """Release the distributed lock."""


class PostgresAdvisorySchedulerLock:
    """
    Hold a PostgreSQL session advisory lock.

    The lock uses its own dedicated SQLAlchemy connection.
    Scheduler-cycle commits therefore cannot release or
    transfer the advisory lock unexpectedly.
    """

    MIN_LOCK_KEY = -(2**63)
    MAX_LOCK_KEY = (2**63) - 1

    def __init__(
        self,
        *,
        engine: Engine,
        lock_key: int,
    ) -> None:
        if engine.dialect.name != "postgresql":
            raise ValueError(
                "PostgreSQL advisory scheduler lock "
                "requires a PostgreSQL engine."
            )

        if not (
            self.MIN_LOCK_KEY
            <= lock_key
            <= self.MAX_LOCK_KEY
        ):
            raise ValueError(
                "PostgreSQL advisory lock key must "
                "fit in a signed 64-bit integer."
            )

        self._engine = engine
        self._lock_key = lock_key
        self._connection: Connection | None = None

    @property
    def held(self) -> bool:
        return self._connection is not None

    def try_acquire(self) -> bool:
        if self._connection is not None:
            raise RuntimeError(
                "Scheduler advisory lock is "
                "already acquired by this instance."
            )

        connection = self._engine.connect()

        try:
            acquired = bool(
                connection.execute(
                    text(
                        "SELECT "
                        "pg_try_advisory_lock"
                        "(:lock_key)"
                    ),
                    {
                        "lock_key": (
                            self._lock_key
                        )
                    },
                ).scalar_one()
            )
        except Exception:
            connection.close()
            raise

        if not acquired:
            connection.close()
            return False

        self._connection = connection
        return True

    def release(self) -> None:
        connection = self._connection

        if connection is None:
            return

        self._connection = None

        try:
            released = bool(
                connection.execute(
                    text(
                        "SELECT "
                        "pg_advisory_unlock"
                        "(:lock_key)"
                    ),
                    {
                        "lock_key": (
                            self._lock_key
                        )
                    },
                ).scalar_one()
            )

            if not released:
                raise RuntimeError(
                    "PostgreSQL did not release "
                    "the scheduler advisory lock."
                )
        except Exception:
            # Invalidating closes the underlying DB
            # connection instead of returning a possibly
            # locked connection back to the pool.
            connection.invalidate()
            raise
        finally:
            connection.close()
