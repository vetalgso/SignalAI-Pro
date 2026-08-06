from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable

from app.tradinggpt.scheduler.background_loop import (
    SchedulerBackgroundLoop,
)


async def wait_until(
    predicate: Callable[[], bool],
    *,
    timeout: float = 1.0,
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout

    while not predicate():
        if loop.time() >= deadline:
            raise AssertionError(
                "Condition was not reached "
                "before timeout."
            )

        await asyncio.sleep(0.005)


def test_initial_status_is_stopped() -> None:
    background = SchedulerBackgroundLoop(
        tick_callback=lambda: {
            "action": "SKIPPED_DISABLED"
        },
        poll_interval_seconds=0.01,
    )

    status = background.status()

    assert status.running is False
    assert status.stopping is False
    assert status.iterations == 0
    assert status.failed_ticks == 0
    assert status.started_at is None


def test_loop_starts_executes_and_stops() -> None:
    async def scenario() -> None:
        calls = 0

        def callback() -> dict[str, object]:
            nonlocal calls
            calls += 1

            return {
                "action": "SKIPPED_DISABLED"
            }

        background = SchedulerBackgroundLoop(
            tick_callback=callback,
            poll_interval_seconds=0.01,
        )

        assert await background.start() is True

        await wait_until(
            lambda: calls >= 2
        )

        assert await background.stop() is True

        status = background.status()

        assert status.running is False
        assert status.iterations >= 2
        assert (
            status.last_action
            == "SKIPPED_DISABLED"
        )
        assert status.started_at is not None
        assert status.stopped_at is not None

    asyncio.run(scenario())


def test_start_is_idempotent() -> None:
    async def scenario() -> None:
        background = SchedulerBackgroundLoop(
            tick_callback=lambda: {
                "action": "SKIPPED_DISABLED"
            },
            poll_interval_seconds=0.02,
        )

        assert await background.start() is True
        assert await background.start() is False
        assert await background.stop() is True

    asyncio.run(scenario())


def test_stop_is_idempotent() -> None:
    async def scenario() -> None:
        background = SchedulerBackgroundLoop(
            tick_callback=lambda: {
                "action": "SKIPPED_DISABLED"
            },
            poll_interval_seconds=0.02,
        )

        assert await background.stop() is False
        assert await background.start() is True
        assert await background.stop() is True
        assert await background.stop() is False

    asyncio.run(scenario())


def test_loop_survives_callback_exception() -> None:
    async def scenario() -> None:
        calls = 0

        def callback() -> dict[str, object]:
            nonlocal calls
            calls += 1

            if calls == 1:
                raise RuntimeError(
                    "Synthetic loop failure."
                )

            return {
                "action": "SKIPPED_DISABLED"
            }

        background = SchedulerBackgroundLoop(
            tick_callback=callback,
            poll_interval_seconds=0.01,
        )

        await background.start()

        await wait_until(
            lambda: (
                background.status().iterations
                >= 2
            )
        )

        await background.stop()

        status = background.status()

        assert status.failed_ticks == 1
        assert status.iterations >= 2
        assert (
            status.last_action
            == "SKIPPED_DISABLED"
        )
        assert status.last_error is None

    asyncio.run(scenario())


def test_ticks_never_overlap() -> None:
    async def scenario() -> None:
        active = 0
        max_active = 0
        calls = 0
        lock = threading.Lock()

        def callback() -> dict[str, object]:
            nonlocal active
            nonlocal max_active
            nonlocal calls

            with lock:
                active += 1
                calls += 1
                max_active = max(
                    max_active,
                    active,
                )

            time.sleep(0.025)

            with lock:
                active -= 1

            return {
                "action": "SKIPPED_DISABLED"
            }

        background = SchedulerBackgroundLoop(
            tick_callback=callback,
            poll_interval_seconds=0.001,
        )

        await background.start()

        await wait_until(
            lambda: calls >= 3
        )

        await background.stop()

        assert max_active == 1

    asyncio.run(scenario())


def test_failed_result_updates_loop_status() -> None:
    async def scenario() -> None:
        background = SchedulerBackgroundLoop(
            tick_callback=lambda: {
                "action": "FAILED",
                "reason": "Synthetic tick failure.",
            },
            poll_interval_seconds=0.05,
        )

        await background.start()

        await wait_until(
            lambda: (
                background.status().iterations
                >= 1
            )
        )

        await background.stop()

        status = background.status()

        assert status.failed_ticks >= 1
        assert status.last_action == "FAILED"
        assert (
            status.last_error
            == "Synthetic tick failure."
        )

    asyncio.run(scenario())
