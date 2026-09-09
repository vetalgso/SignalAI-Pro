from __future__ import annotations

from pathlib import Path

import pytest

from app.tradinggpt.signals import (
    telegram_background,
)


class FakeLock:
    def __init__(
        self,
        *,
        acquired: bool,
    ) -> None:
        self.acquired = acquired
        self.acquire_calls = 0
        self.release_calls = 0

    def try_acquire(self) -> bool:
        self.acquire_calls += 1
        return self.acquired

    def release(self) -> None:
        self.release_calls += 1


class FakeSessionContext:
    def __init__(self) -> None:
        self.session = object()
        self.enter_calls = 0
        self.exit_calls = 0

    def __enter__(self) -> object:
        self.enter_calls += 1
        return self.session

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        self.exit_calls += 1


class FakeRepository:
    instances: list[
        "FakeRepository"
    ] = []

    def __init__(
        self,
        session: object,
    ) -> None:
        self.session = session
        self.instances.append(self)


class FakePublisher:
    instances: list[
        "FakePublisher"
    ] = []

    def __init__(
        self,
        **kwargs: object,
    ) -> None:
        self.kwargs = kwargs
        self.instances.append(self)


class FakeDispatcher:
    instances: list[
        "FakeDispatcher"
    ] = []
    result: dict[str, object] = {
        "action": "IDLE",
        "claimed": 0,
        "sent": 0,
        "retried": 0,
        "skipped": 0,
        "failed": 0,
        "recovered": 0,
        "exhausted": 0,
        "errors": [],
    }
    error: Exception | None = None

    def __init__(
        self,
        **kwargs: object,
    ) -> None:
        self.kwargs = kwargs
        self.instances.append(self)

    async def dispatch_once(
        self,
    ) -> dict[str, object]:
        if self.error is not None:
            raise self.error

        return dict(self.result)


@pytest.fixture(autouse=True)
def reset_fakes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeRepository.instances = []
    FakePublisher.instances = []
    FakeDispatcher.instances = []
    FakeDispatcher.error = None
    FakeDispatcher.result = {
        "action": "IDLE",
        "claimed": 0,
        "sent": 0,
        "retried": 0,
        "skipped": 0,
        "failed": 0,
        "recovered": 0,
        "exhausted": 0,
        "errors": [],
    }

    monkeypatch.setattr(
        telegram_background,
        "TelegramDeliveryRepository",
        FakeRepository,
    )
    monkeypatch.setattr(
        telegram_background,
        "TelegramSignalPublisher",
        FakePublisher,
    )
    monkeypatch.setattr(
        telegram_background,
        "TelegramSignalDispatcher",
        FakeDispatcher,
    )


def configure_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        telegram_background.settings,
        "telegram_signal_enabled",
        True,
    )
    monkeypatch.setattr(
        telegram_background.settings,
        "telegram_signal_bot_token",
        "test-token",
    )
    monkeypatch.setattr(
        telegram_background.settings,
        "telegram_signal_chat_id",
        "-100123",
    )


def test_tick_skips_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        telegram_background.settings,
        "telegram_signal_enabled",
        False,
    )
    monkeypatch.setattr(
        telegram_background,
        "PostgresAdvisorySchedulerLock",
        lambda **_: pytest.fail(
            "Disabled tick must not create lock."
        ),
    )

    result = (
        telegram_background
        .run_telegram_signal_background_tick()
    )

    assert (
        result["action"]
        == "SKIPPED_DISABLED"
    )
    assert FakeDispatcher.instances == []


def test_tick_rejects_missing_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_enabled(monkeypatch)

    monkeypatch.setattr(
        telegram_background.settings,
        "telegram_signal_bot_token",
        "",
    )
    monkeypatch.setattr(
        telegram_background,
        "PostgresAdvisorySchedulerLock",
        lambda **_: pytest.fail(
            "Invalid configuration "
            "must not create lock."
        ),
    )

    result = (
        telegram_background
        .run_telegram_signal_background_tick()
    )

    assert result["action"] == "FAILED"
    assert "credentials" in result["reason"]
    assert FakeDispatcher.instances == []


def test_tick_skips_when_lock_is_held(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_enabled(monkeypatch)
    lock = FakeLock(acquired=False)

    monkeypatch.setattr(
        telegram_background,
        "PostgresAdvisorySchedulerLock",
        lambda **_: lock,
    )
    monkeypatch.setattr(
        telegram_background,
        "SessionLocal",
        lambda: pytest.fail(
            "Locked tick must not open session."
        ),
    )

    result = (
        telegram_background
        .run_telegram_signal_background_tick()
    )

    assert result["action"] == "SKIPPED_LOCKED"
    assert lock.acquire_calls == 1
    assert lock.release_calls == 0


def test_tick_dispatches_and_releases_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_enabled(monkeypatch)
    lock = FakeLock(acquired=True)
    session = FakeSessionContext()

    FakeDispatcher.result = {
        "action": "COMPLETED",
        "claimed": 1,
        "sent": 1,
        "retried": 0,
        "skipped": 0,
        "failed": 0,
        "recovered": 0,
        "exhausted": 0,
        "errors": [],
    }

    monkeypatch.setattr(
        telegram_background,
        "PostgresAdvisorySchedulerLock",
        lambda **_: lock,
    )
    monkeypatch.setattr(
        telegram_background,
        "SessionLocal",
        lambda: session,
    )

    result = (
        telegram_background
        .run_telegram_signal_background_tick()
    )

    assert result["action"] == "COMPLETED"
    assert result["sent"] == 1
    assert lock.release_calls == 1
    assert session.enter_calls == 1
    assert session.exit_calls == 1

    assert len(FakePublisher.instances) == 1
    assert (
        FakePublisher.instances[0]
        .kwargs["enabled"]
        is True
    )
    assert (
        FakePublisher.instances[0]
        .kwargs["bot_token"]
        == "test-token"
    )

    assert len(FakeDispatcher.instances) == 1
    assert (
        FakeDispatcher.instances[0]
        .kwargs["repository"]
        is FakeRepository.instances[0]
    )


def test_tick_releases_lock_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_enabled(monkeypatch)
    lock = FakeLock(acquired=True)
    session = FakeSessionContext()

    FakeDispatcher.error = RuntimeError(
        "Synthetic dispatcher failure."
    )

    monkeypatch.setattr(
        telegram_background,
        "PostgresAdvisorySchedulerLock",
        lambda **_: lock,
    )
    monkeypatch.setattr(
        telegram_background,
        "SessionLocal",
        lambda: session,
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic dispatcher failure",
    ):
        (
            telegram_background
            .run_telegram_signal_background_tick()
        )

    assert lock.release_calls == 1
    assert session.exit_calls == 1


def test_partial_result_gets_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_enabled(monkeypatch)
    lock = FakeLock(acquired=True)
    session = FakeSessionContext()

    FakeDispatcher.result = {
        "action": "PARTIAL",
        "claimed": 1,
        "sent": 0,
        "retried": 1,
        "skipped": 0,
        "failed": 0,
        "recovered": 0,
        "exhausted": 0,
        "errors": [
            {
                "signal_id": 42,
                "reason": (
                    "Temporary Telegram failure."
                ),
            },
        ],
    }

    monkeypatch.setattr(
        telegram_background,
        "PostgresAdvisorySchedulerLock",
        lambda **_: lock,
    )
    monkeypatch.setattr(
        telegram_background,
        "SessionLocal",
        lambda: session,
    )

    result = (
        telegram_background
        .run_telegram_signal_background_tick()
    )

    assert result["action"] == "PARTIAL"
    assert (
        result["reason"]
        == "Temporary Telegram failure."
    )
    assert lock.release_calls == 1


def test_main_lifecycle_contract() -> None:
    main = Path(
        "app/main.py"
    ).read_text(encoding="utf-8")

    for value in (
        "telegram_signal_background_loop",
        "telegram_signal_loop_started",
        "telegram_signal_enabled",
    ):
        assert value in main, value

    start_state_index = main.index(
        (
            "telegram_signal_loop_started "
            "= await"
        )
    )
    start_call_index = main.index(
        ".start()",
        start_state_index,
    )

    stop_guard_index = main.index(
        "if telegram_signal_loop_started:"
    )
    stop_call_index = main.index(
        ".stop()",
        stop_guard_index,
    )

    assert start_call_index > start_state_index
    assert stop_call_index > stop_guard_index
