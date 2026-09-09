from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.database.session import SessionLocal

from .lifecycle import (
    SignalLifecycleTracker,
)
from .repository import (
    TradingSignalRepository,
)
from .lifecycle_journal import LifecycleJournal, safe_error_code


logger = logging.getLogger(__name__)


async def refresh_product_signals(
) -> dict[str, object]:
    journal = LifecycleJournal(SessionLocal, settings.signal_tracking_interval_seconds)
    journal.begin()
    try:
        with SessionLocal() as session:
            tracker = SignalLifecycleTracker(
                TradingSignalRepository(session)
            )
            result = await tracker.refresh_all()
    except asyncio.CancelledError:
        journal.cancel()
        raise
    except Exception as exc:
        journal.fail(exc)
        raise
    journal.complete(result)
    return result


class SignalLifecycleBackgroundLoop:
    def __init__(
        self,
        interval_seconds: float,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError(
                "Signal tracking interval "
                "must be positive."
            )

        self.interval_seconds = (
            interval_seconds
        )
        self._task: (
            asyncio.Task[None] | None
        ) = None
        self._stop_event: (
            asyncio.Event | None
        ) = None

    async def start(self) -> bool:
        if (
            self._task is not None
            and not self._task.done()
        ):
            return False

        self._stop_event = asyncio.Event()

        self._task = asyncio.create_task(
            self._run(),
            name=(
                "signal-lifecycle-loop"
            ),
        )

        return True

    async def stop(self) -> bool:
        task = self._task

        if task is None or task.done():
            return False

        if self._stop_event is not None:
            self._stop_event.set()

        await task
        self._task = None

        return True

    async def _run(self) -> None:
        stop_event = self._stop_event

        if stop_event is None:
            return

        while not stop_event.is_set():
            try:
                result = await (
                    refresh_product_signals()
                )

                if result.get(
                    "transition_count"
                ):
                    logger.info(
                        "Signal lifecycle "
                        "transitions: %s",
                        result[
                            "transition_count"
                        ],
                    )
            except Exception as exc:
                logger.error(
                    "Signal lifecycle refresh failed; code=%s",
                    safe_error_code(exc),
                )

            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=(
                        self.interval_seconds
                    ),
                )
            except TimeoutError:
                continue


signal_lifecycle_background_loop = (
    SignalLifecycleBackgroundLoop(
        interval_seconds=(
            settings
            .signal_tracking_interval_seconds
        )
    )
)
