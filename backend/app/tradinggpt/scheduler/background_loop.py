from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class SchedulerBackgroundLoopStatus:
    running: bool
    stopping: bool
    poll_interval_seconds: float
    iterations: int
    failed_ticks: int
    started_at: datetime | None
    stopped_at: datetime | None
    last_tick_started_at: datetime | None
    last_tick_finished_at: datetime | None
    last_action: str | None
    last_error: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class SchedulerBackgroundLoop:
    """
    Run safe scheduler ticks sequentially.

    The loop does not enable the scheduler and does not
    bypass SchedulerState. Each callback must perform a
    regular non-forced scheduler runner tick.
    """

    def __init__(
        self,
        *,
        tick_callback: Callable[
            [],
            dict[str, object],
        ],
        poll_interval_seconds: float = 5.0,
        task_name: str = (
            "tradinggpt-scheduler-loop"
        ),
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError(
                "Background poll interval must be "
                "greater than zero."
            )

        if not task_name.strip():
            raise ValueError(
                "Background task name must not "
                "be empty."
            )

        self._tick_callback = tick_callback
        self._task_name = task_name
        self._poll_interval_seconds = (
            poll_interval_seconds
        )
        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None

        self._iterations = 0
        self._failed_ticks = 0
        self._started_at: datetime | None = None
        self._stopped_at: datetime | None = None
        self._last_tick_started_at: (
            datetime | None
        ) = None
        self._last_tick_finished_at: (
            datetime | None
        ) = None
        self._last_action: str | None = None
        self._last_error: str | None = None

    async def start(self) -> bool:
        if (
            self._task is not None
            and not self._task.done()
        ):
            return False

        self._stop_event = asyncio.Event()
        self._started_at = datetime.now(
            timezone.utc
        )
        self._stopped_at = None

        self._task = asyncio.create_task(
            self._run(),
            name=self._task_name,
        )

        return True

    async def stop(self) -> bool:
        task = self._task

        if task is None or task.done():
            return False

        stop_event = self._stop_event

        if stop_event is not None:
            stop_event.set()

        await task
        self._task = None

        return True

    def status(
        self,
    ) -> SchedulerBackgroundLoopStatus:
        running = (
            self._task is not None
            and not self._task.done()
        )
        stopping = (
            running
            and self._stop_event is not None
            and self._stop_event.is_set()
        )

        return SchedulerBackgroundLoopStatus(
            running=running,
            stopping=stopping,
            poll_interval_seconds=(
                self._poll_interval_seconds
            ),
            iterations=self._iterations,
            failed_ticks=self._failed_ticks,
            started_at=self._started_at,
            stopped_at=self._stopped_at,
            last_tick_started_at=(
                self._last_tick_started_at
            ),
            last_tick_finished_at=(
                self._last_tick_finished_at
            ),
            last_action=self._last_action,
            last_error=self._last_error,
        )

    async def _run(self) -> None:
        stop_event = self._stop_event

        if stop_event is None:
            raise RuntimeError(
                "Background loop stop event "
                "is not initialized."
            )

        try:
            while not stop_event.is_set():
                await self._run_tick()

                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=(
                            self
                            ._poll_interval_seconds
                        ),
                    )
                except TimeoutError:
                    continue
        finally:
            self._stopped_at = datetime.now(
                timezone.utc
            )

    async def _run_tick(self) -> None:
        self._last_tick_started_at = (
            datetime.now(timezone.utc)
        )

        try:
            result = await asyncio.to_thread(
                self._tick_callback
            )
        except Exception as exc:
            self._failed_ticks += 1
            self._last_action = "LOOP_ERROR"
            self._last_error = str(exc)
        else:
            action = result.get("action")
            self._last_action = (
                str(action)
                if action is not None
                else None
            )

            if self._last_action == "FAILED":
                self._failed_ticks += 1
                self._last_error = str(
                    result.get("reason")
                    or "Scheduler tick failed."
                )
            else:
                self._last_error = None
        finally:
            self._iterations += 1
            self._last_tick_finished_at = (
                datetime.now(timezone.utc)
            )
