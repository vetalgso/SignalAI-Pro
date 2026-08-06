from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app import main as main_module


class FakeBackgroundLoop:
    def __init__(
        self,
        *,
        start_result: bool = True,
    ) -> None:
        self.start_result = start_result
        self.start_calls = 0
        self.stop_calls = 0

    async def start(self) -> bool:
        self.start_calls += 1
        return self.start_result

    async def stop(self) -> bool:
        self.stop_calls += 1
        return True


def test_lifespan_starts_and_stops_loop(
    monkeypatch,
) -> None:
    fake = FakeBackgroundLoop()

    monkeypatch.setattr(
        main_module,
        "scheduler_background_loop",
        fake,
    )
    monkeypatch.setattr(
        main_module,
        "settings",
        SimpleNamespace(
            scheduler_background_loop_enabled=True
        ),
    )

    async def scenario() -> None:
        async with main_module.lifespan(
            main_module.app
        ):
            assert fake.start_calls == 1
            assert fake.stop_calls == 0

        assert fake.stop_calls == 1

    asyncio.run(scenario())


def test_lifespan_respects_disabled_setting(
    monkeypatch,
) -> None:
    fake = FakeBackgroundLoop()

    monkeypatch.setattr(
        main_module,
        "scheduler_background_loop",
        fake,
    )
    monkeypatch.setattr(
        main_module,
        "settings",
        SimpleNamespace(
            scheduler_background_loop_enabled=False
        ),
    )

    async def scenario() -> None:
        async with main_module.lifespan(
            main_module.app
        ):
            pass

    asyncio.run(scenario())

    assert fake.start_calls == 0
    assert fake.stop_calls == 0


def test_lifespan_does_not_stop_existing_loop(
    monkeypatch,
) -> None:
    fake = FakeBackgroundLoop(
        start_result=False
    )

    monkeypatch.setattr(
        main_module,
        "scheduler_background_loop",
        fake,
    )
    monkeypatch.setattr(
        main_module,
        "settings",
        SimpleNamespace(
            scheduler_background_loop_enabled=True
        ),
    )

    async def scenario() -> None:
        async with main_module.lifespan(
            main_module.app
        ):
            pass

    asyncio.run(scenario())

    assert fake.start_calls == 1
    assert fake.stop_calls == 0
