from datetime import (
    datetime,
    timedelta,
    timezone,
)
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.signal_discovery import (
    SignalScanRun,
)
from app.models.trading_signal import (
    TelegramSignalDelivery,
    TradingSignal,
    TradingSignalEvent,
)
from app.tradinggpt.scheduler.background_loop import (
    SchedulerBackgroundLoopStatus,
)
from app.tradinggpt.signals.runtime_metrics import (
    PROMETHEUS_CONTENT_TYPE,
    SignalPipelineMetricsService,
)


NOW = datetime(
    2026,
    8,
    28,
    9,
    0,
    tzinfo=timezone.utc,
)


def _status(
    *,
    action: str,
    failed_ticks: int = 0,
    error: str | None = None,
) -> SchedulerBackgroundLoopStatus:
    return SchedulerBackgroundLoopStatus(
        running=True,
        stopping=False,
        poll_interval_seconds=15.0,
        iterations=10,
        failed_ticks=failed_ticks,
        started_at=(
            NOW - timedelta(hours=1)
        ),
        stopped_at=None,
        last_tick_started_at=(
            NOW - timedelta(seconds=5)
        ),
        last_tick_finished_at=(
            NOW - timedelta(seconds=3)
        ),
        last_action=action,
        last_error=error,
    )


def _session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    SignalScanRun.__table__.create(engine)
    TradingSignal.__table__.create(engine)
    TradingSignalEvent.__table__.create(
        engine
    )
    TelegramSignalDelivery.__table__.create(
        engine
    )

    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    return engine, factory()


def _signal() -> TradingSignal:
    return TradingSignal(
        fingerprint="metrics-signal",
        exchange="BINANCE",
        market_type="SPOT",
        symbol="BTCUSDT",
        timeframe="1H",
        side="LONG",
        strategy="TEST",
        status="ACTIVE",
        confidence=Decimal("75"),
        risk_level="MEDIUM",
        risk_reward=Decimal("1.5"),
        entry_min=Decimal("100"),
        entry_max=Decimal("101"),
        stop_loss=Decimal("95"),
        take_profit_1=Decimal("105"),
        take_profit_2=Decimal("110"),
        take_profit_3=Decimal("115"),
        current_price=Decimal("100"),
        reasons=[],
        metadata_payload={},
        source="TEST",
        generated_at=NOW,
        expires_at=(
            NOW + timedelta(hours=4)
        ),
        activated_at=NOW,
    )


def test_signal_pipeline_metrics() -> None:
    engine, session = _session()

    try:
        signal = _signal()
        session.add(signal)
        session.flush()

        session.add_all(
            [
                TelegramSignalDelivery(
                    signal_id=signal.id,
                    delivery_type=(
                        "SIGNAL_CREATED"
                    ),
                    status="SENT",
                    created_at=(
                        NOW
                        - timedelta(minutes=10)
                    ),
                    next_attempt_at=NOW,
                ),
                TelegramSignalDelivery(
                    signal_id=signal.id,
                    delivery_type=(
                        "SIGNAL_STATUS_CHANGED"
                    ),
                    status="PENDING",
                    created_at=(
                        NOW
                        - timedelta(seconds=90)
                    ),
                    next_attempt_at=NOW,
                ),
                TelegramSignalDelivery(
                    signal_id=signal.id,
                    delivery_type=(
                        "SIGNAL_STATUS_CHANGED"
                    ),
                    status="FAILED",
                    created_at=(
                        NOW
                        - timedelta(seconds=30)
                    ),
                    next_attempt_at=NOW,
                ),
            ]
        )
        session.add(
            SignalScanRun(
                status="COMPLETED",
                universe_source="TEST",
                risk_level="MEDIUM",
                minimum_confidence=Decimal("60"),
                requested_limit=3,
                universe_assets=[
                    "BTC",
                    "ETH",
                    "SOL",
                ],
                scanned_assets=3,
                successful_assets=1,
                failed_assets=2,
                opportunities_found=0,
                created_count=0,
                duplicate_count=0,
                skipped_count=1,
                rejection_reasons={},
                scanner_errors=[
                    {
                        "asset": "ETH",
                        "error": "TimeoutError",
                        "error_code": (
                            "UPSTREAM_TIMEOUT"
                        ),
                        "stage": "ASSET_ANALYSIS",
                        "location": (
                            "provider.py:load:42"
                        ),
                    },
                    {
                        "asset": "SOL",
                        "error": "CustomFailure",
                        "error_code": (
                            "ARBITRARY_UNBOUNDED_CODE"
                        ),
                        "stage": "ASSET_ANALYSIS",
                        "location": (
                            "scanner.py:analyze:77"
                        ),
                    },
                ],
                started_at=(
                    NOW - timedelta(seconds=15)
                ),
                completed_at=(
                    NOW - timedelta(seconds=3)
                ),
                created_at=(
                    NOW - timedelta(seconds=15)
                ),
            )
        )
        session.commit()

        metrics = SignalPipelineMetricsService(
            session=session,
            scanner_enabled=True,
            telegram_enabled=True,
            scanner_status_provider=(
                lambda: _status(
                    action="COMPLETED"
                )
            ),
            telegram_status_provider=(
                lambda: _status(
                    action="PARTIAL",
                    failed_ticks=1,
                    error="temporary failure",
                )
            ),
            now_provider=lambda: NOW,
        ).render()

        required = (
            (
                "signalai_signal_scanner_"
                "background_running 1"
            ),
            (
                "signalai_signal_scanner_"
                "seconds_since_last_tick 3"
            ),
            (
                "signalai_signal_scanner_"
                "last_action_info"
                '{action="COMPLETED"} 1'
            ),
            (
                "signalai_telegram_signal_"
                "dispatcher_last_tick_failed 1"
            ),
            (
                "signalai_telegram_signal_"
                "dispatcher_last_action_info"
                '{action="PARTIAL"} 1'
            ),
            (
                "signalai_telegram_signal_"
                "outbox_deliveries"
                '{delivery_type="SIGNAL_CREATED",'
                'status="SENT"} 1'
            ),
            (
                "signalai_telegram_signal_"
                "outbox_deliveries"
                '{delivery_type='
                '"SIGNAL_STATUS_CHANGED",'
                'status="PENDING"} 1'
            ),
            (
                "signalai_telegram_signal_"
                "outbox_in_flight 1"
            ),
            (
                "signalai_telegram_signal_"
                "outbox_failed 1"
            ),
            (
                "signalai_telegram_signal_"
                "outbox_oldest_in_flight_"
                "age_seconds 90"
            ),
            (
                "signalai_trading_signals_"
                "trackable 1"
            ),
            (
                "signalai_signal_scanner_"
                "latest_run_observed 1"
            ),
            (
                "signalai_signal_scanner_"
                "latest_run_failed_assets 2"
            ),
            (
                "signalai_signal_scanner_"
                "latest_run_errors"
                '{error_code="UPSTREAM_TIMEOUT"} 1'
            ),
            (
                "signalai_signal_scanner_"
                "latest_run_errors"
                '{error_code="UNKNOWN"} 1'
            ),
            (
                "signalai_signal_scanner_"
                "latest_run_errors"
                '{error_code="INVALID_ANALYSIS_PAYLOAD"} 0'
            ),
        )

        for value in required:
            assert value in metrics, value

        assert (
            "ARBITRARY_UNBOUNDED_CODE"
            not in metrics
        )
    finally:
        session.close()
        engine.dispose()


def test_metric_labels_are_bounded() -> None:
    engine, session = _session()

    try:
        metrics = SignalPipelineMetricsService(
            session=session,
            scanner_enabled=False,
            telegram_enabled=False,
            scanner_status_provider=(
                lambda: _status(
                    action="UNBOUNDED_ACTION"
                )
            ),
            telegram_status_provider=(
                lambda: _status(
                    action="IDLE"
                )
            ),
            now_provider=lambda: NOW,
        ).render()

        assert (
            'last_action_info'
            '{action="UNKNOWN"} 1'
            in metrics
        )
        assert "UNBOUNDED_ACTION" not in metrics
    finally:
        session.close()
        engine.dispose()


def test_ai_promotion_metrics_current_state_and_bounded_labels() -> None:
    engine, session = _session()
    statuses = (
        "ACTIVE", "ENTRY_REACHED", "TP1_REACHED", "TP2_REACHED",
        "TP3_REACHED", "STOPPED", "EXPIRED", "CANCELLED", "UNKNOWN",
    )
    service = SignalPipelineMetricsService(
        session=session,
        scanner_enabled=False,
        telegram_enabled=False,
        scanner_status_provider=lambda: _status(action="IDLE"),
        telegram_status_provider=lambda: _status(action="IDLE"),
        now_provider=lambda: NOW,
    )

    def check(expected: dict[str, int]) -> None:
        metrics = service.render()
        lines = metrics.splitlines()
        assert (
            f"signalai_signal_ai_promotions {sum(expected.values())}"
            in lines
        )
        actual = {
            line for line in lines
            if line.startswith("signalai_signal_ai_promotions_by_status{")
        }
        wanted = {
            'signalai_signal_ai_promotions_by_status'
            f'{{status="{status}"}} {expected.get(status, 0)}'
            for status in statuses
        }
        assert actual == wanted
        assert "UNBOUNDED_STATUS" not in metrics
        assert "OTHER_STATUS" not in metrics
        assert "BTCUSDT" not in metrics
        assert "# TYPE signalai_signal_ai_promotions gauge" in lines
        assert (
            "# TYPE signalai_signal_ai_promotions_by_status gauge"
            in lines
        )

    try:
        check({})

        # Non-AI signals must not contribute.
        manual = _signal()
        session.add(manual)
        session.commit()
        check({})

        promoted = []
        for index, status in enumerate(statuses[:-1]):
            signal = _signal()
            signal.fingerprint = f"ai-metrics-{index}"
            signal.source = "AI_REVIEW"
            signal.status = status
            session.add(signal)
            promoted.append(signal)
        for index, status in enumerate(("UNBOUNDED_STATUS", "OTHER_STATUS")):
            signal = _signal()
            signal.fingerprint = f"ai-unknown-{index}"
            signal.source = "AI_REVIEW"
            signal.status = status
            session.add(signal)
        session.commit()

        expected = {status: 1 for status in statuses[:-1]}
        expected["UNKNOWN"] = 2
        check(expected)

        # A lifecycle transition moves a row, not the total.
        promoted[0].status = "STOPPED"
        session.commit()
        expected["ACTIVE"] = 0
        expected["STOPPED"] = 2
        check(expected)
    finally:
        session.close()
        engine.dispose()


def test_metrics_endpoint_contract() -> None:
    from pathlib import Path

    router = Path(
        "app/tradinggpt/signals/router.py"
    ).read_text(encoding="utf-8")

    assert '"/runtime/metrics"' in router
    assert (
        "SignalPipelineMetricsService"
        in router
    )
    assert "PROMETHEUS_CONTENT_TYPE" in router
    assert (
        PROMETHEUS_CONTENT_TYPE
        == (
            "text/plain; version=0.0.4; "
            "charset=utf-8"
        )
    )
