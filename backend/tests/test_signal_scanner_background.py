from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.tradinggpt.signals import (
    scanner_background,
)


class FakeLock:
    def __init__(
        self,
        acquired: bool = True,
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
    def __enter__(self) -> object:
        return object()

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        return None


class FakeRepository:
    trackable: list[object] = []

    def __init__(
        self,
        session: object,
    ) -> None:
        self.session = session

    def list_trackable(
        self,
        *,
        limit: int,
    ) -> list[object]:
        assert limit == 500
        return list(self.trackable)


class FakeService:
    def __init__(
        self,
        repository: object,
    ) -> None:
        self.repository = repository


class FakeDiscoveryRun:
    id = 701


class FakeDiscoveryRepository:
    calls: list[dict[str, object]] = []

    def __init__(self, session: object) -> None:
        self.session = session

    def record_completed_scan(
        self,
        **values: object,
    ) -> FakeDiscoveryRun:
        self.calls.append(values)
        return FakeDiscoveryRun()


class FakeGenerator:
    calls: list[dict[str, object]] = []

    def __init__(
        self,
        service: object,
    ) -> None:
        self.service = service

    def persist_scan(
        self,
        *,
        scan_result: dict[str, object],
        min_confidence: Decimal,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "scan_result": scan_result,
                "min_confidence": (
                    min_confidence
                ),
            }
        )

        opportunities = scan_result.get(
            "opportunities",
            [],
        )

        created = [
            SimpleNamespace(id=101 + index)
            for index, _
            in enumerate(opportunities)
        ]

        return {
            "created_count": len(created),
            "duplicate_count": 0,
            "skipped_count": 0,
            "created": created,
        }


@pytest.fixture(autouse=True)
def reset_fakes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeRepository.trackable = []
    FakeGenerator.calls = []
    FakeDiscoveryRepository.calls = []

    monkeypatch.setattr(
        scanner_background,
        "TradingSignalRepository",
        FakeRepository,
    )
    monkeypatch.setattr(
        scanner_background,
        "TradingSignalService",
        FakeService,
    )
    monkeypatch.setattr(
        scanner_background,
        "TradingSignalGenerator",
        FakeGenerator,
    )
    monkeypatch.setattr(
        scanner_background,
        "SignalDiscoveryRepository",
        FakeDiscoveryRepository,
    )


def configure_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = (
        scanner_background.settings
    )

    monkeypatch.setattr(
        settings,
        "signal_scanner_background_enabled",
        True,
    )
    monkeypatch.setattr(
        settings,
        "signal_scanner_interval_seconds",
        900.0,
    )
    monkeypatch.setattr(
        settings,
        "signal_scanner_risk_level",
        "medium",
    )
    monkeypatch.setattr(
        settings,
        "signal_scanner_market_limit",
        10,
    )
    monkeypatch.setattr(
        settings,
        "signal_scanner_min_confidence",
        60.0,
    )
    monkeypatch.setattr(
        settings,
        "signal_scanner_advisory_lock_key",
        2026082801,
    )
    monkeypatch.setattr(
        scanner_background.settings,
        "signal_ai_review_enabled",
        False,
    )


def test_disabled_tick_does_not_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        scanner_background.settings,
        "signal_scanner_background_enabled",
        False,
    )
    monkeypatch.setattr(
        scanner_background,
        "PostgresAdvisorySchedulerLock",
        lambda **_: pytest.fail(
            "Disabled scanner created a lock."
        ),
    )

    result = (
        scanner_background
        .run_signal_scanner_background_tick()
    )

    assert (
        result["action"]
        == "SKIPPED_DISABLED"
    )


def test_locked_tick_does_not_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_enabled(monkeypatch)
    lock = FakeLock(acquired=False)

    monkeypatch.setattr(
        scanner_background,
        "PostgresAdvisorySchedulerLock",
        lambda **_: lock,
    )
    monkeypatch.setattr(
        scanner_background,
        "SessionLocal",
        lambda: pytest.fail(
            "Locked scanner opened a session."
        ),
    )

    result = (
        scanner_background
        .run_signal_scanner_background_tick()
    )

    assert result["action"] == "SKIPPED_LOCKED"
    assert lock.release_calls == 0


def test_scans_top_ten_and_persists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_enabled(monkeypatch)
    lock = FakeLock()
    captured: dict[str, object] = {}

    async def scan_market(
        **kwargs: object,
    ) -> dict[str, object]:
        captured.update(kwargs)

        return {
            "scanned_assets": 10,
            "successful_assets": 10,
            "failed_assets": 0,
            "opportunities": [
                {
                    "symbol": "BTCUSDT",
                },
            ],
        }

    monkeypatch.setattr(
        scanner_background,
        "PostgresAdvisorySchedulerLock",
        lambda **_: lock,
    )
    monkeypatch.setattr(
        scanner_background,
        "SessionLocal",
        FakeSessionContext,
    )
    monkeypatch.setattr(
        scanner_background.tradinggpt,
        "scan_market",
        scan_market,
    )

    result = (
        scanner_background
        .run_signal_scanner_background_tick()
    )

    assert captured == {
        "assets": None,
        "risk_level": "medium",
        "limit": 10,
    }
    assert result["action"] == "COMPLETED"
    assert result["created_count"] == 1
    assert result["created_signal_ids"] == [
        101,
    ]
    assert result["discovery_run_id"] == 701
    assert len(FakeDiscoveryRepository.calls) == 1
    assert (
        FakeGenerator.calls[0][
            "min_confidence"
        ]
        == Decimal("60.0")
    )
    assert lock.release_calls == 1


def test_active_symbol_is_suppressed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_enabled(monkeypatch)
    lock = FakeLock()

    FakeRepository.trackable = [
        SimpleNamespace(
            symbol="BTCUSDT"
        ),
    ]

    async def scan_market(
        **_: object,
    ) -> dict[str, object]:
        return {
            "scanned_assets": 2,
            "successful_assets": 2,
            "failed_assets": 0,
            "opportunities": [
                {
                    "symbol": "BTCUSDT",
                },
                {
                    "symbol": "ETHUSDT",
                },
            ],
        }

    monkeypatch.setattr(
        scanner_background,
        "PostgresAdvisorySchedulerLock",
        lambda **_: lock,
    )
    monkeypatch.setattr(
        scanner_background,
        "SessionLocal",
        FakeSessionContext,
    )
    monkeypatch.setattr(
        scanner_background.tradinggpt,
        "scan_market",
        scan_market,
    )

    result = (
        scanner_background
        .run_signal_scanner_background_tick()
    )

    persisted = (
        FakeGenerator.calls[0]
        ["scan_result"]
        ["opportunities"]
    )

    assert persisted == [
        {
            "symbol": "ETHUSDT",
        },
    ]
    assert (
        result["active_signal_skips"]
        == 1
    )
    assert result["created_count"] == 1
    assert lock.release_calls == 1


def test_invalid_risk_level_fails_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_enabled(monkeypatch)

    monkeypatch.setattr(
        scanner_background.settings,
        "signal_scanner_risk_level",
        "extreme",
    )
    monkeypatch.setattr(
        scanner_background,
        "PostgresAdvisorySchedulerLock",
        lambda **_: pytest.fail(
            "Invalid config created a lock."
        ),
    )

    result = (
        scanner_background
        .run_signal_scanner_background_tick()
    )

    assert result["action"] == "FAILED"


def test_main_lifecycle_contract() -> None:
    main = Path(
        "app/main.py"
    ).read_text(encoding="utf-8")

    for value in (
        "signal_scanner_background_loop",
        "signal_scanner_loop_started",
        "signal_scanner_background_enabled",
    ):
        assert value in main, value

    start_state_index = main.index(
        (
            "signal_scanner_loop_started "
            "= await"
        )
    )
    start_call_index = main.index(
        ".start()",
        start_state_index,
    )

    stop_guard_index = main.index(
        "if signal_scanner_loop_started:"
    )
    stop_call_index = main.index(
        ".stop()",
        stop_guard_index,
    )

    assert (
        start_call_index
        > start_state_index
    )
    assert (
        stop_call_index
        > stop_guard_index
    )

def test_scanner_exposes_ai_review_result() -> None:
    source = Path(
        "app/tradinggpt/signals/"
        "scanner_background.py"
    ).read_text(encoding="utf-8")

    assert "SignalAIReviewService" in source
    assert "review_scan_run" in source
    assert '"ai_review": ai_review_result' in source
    assert "settings.signal_ai_review_enabled" in source
