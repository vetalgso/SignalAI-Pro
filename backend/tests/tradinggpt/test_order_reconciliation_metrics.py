from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.main import app
from app.tradinggpt.orders.reconciliation_metrics import (
    OrderReconciliationMetricsService,
)
from app.tradinggpt.orders.reconciliation_metrics_router import (
    get_order_reconciliation_metrics,
)
from app.tradinggpt.scheduler.background_loop import (
    SchedulerBackgroundLoopStatus,
)


def build_status(
    *,
    last_action: str | None = "NO_CANDIDATES",
    last_error: str | None = None,
    failed_ticks: int = 2,
) -> SchedulerBackgroundLoopStatus:
    return SchedulerBackgroundLoopStatus(
        running=True,
        stopping=False,
        poll_interval_seconds=15.0,
        iterations=12,
        failed_ticks=failed_ticks,
        started_at=datetime(
            2026,
            8,
            25,
            8,
            59,
            tzinfo=timezone.utc,
        ),
        stopped_at=None,
        last_tick_started_at=datetime(
            2026,
            8,
            25,
            9,
            0,
            tzinfo=timezone.utc,
        ),
        last_tick_finished_at=datetime(
            2026,
            8,
            25,
            9,
            0,
            5,
            tzinfo=timezone.utc,
        ),
        last_action=last_action,
        last_error=last_error,
    )


def test_reconciliation_metrics_render_runtime(
) -> None:
    service = OrderReconciliationMetricsService(
        enabled=True,
        batch_size=50,
        status_provider=build_status,
        now_provider=lambda: datetime(
            2026,
            8,
            25,
            9,
            0,
            20,
            tzinfo=timezone.utc,
        ),
    )

    metrics = service.render()

    expected = (
        "signalai_order_reconciliation_enabled 1",
        (
            "signalai_order_reconciliation_"
            "read_only 1"
        ),
        (
            "signalai_order_reconciliation_"
            "background_running 1"
        ),
        (
            "signalai_order_reconciliation_"
            "iterations_total 12"
        ),
        (
            "signalai_order_reconciliation_"
            "failed_ticks_total 2"
        ),
        (
            "signalai_order_reconciliation_"
            "poll_interval_seconds 15"
        ),
        (
            "signalai_order_reconciliation_"
            "batch_size 50"
        ),
        (
            "signalai_order_reconciliation_"
            "last_tick_observed 1"
        ),
        (
            "signalai_order_reconciliation_"
            "last_tick_duration_seconds 5"
        ),
        (
            "signalai_order_reconciliation_"
            "seconds_since_last_tick 15"
        ),
        (
            "signalai_order_reconciliation_"
            'last_action_info{'
            'action="NO_CANDIDATES"} 1'
        ),
    )

    for value in expected:
        assert value in metrics

    assert metrics.endswith("\n")


def test_reconciliation_metrics_mark_failed_tick(
) -> None:
    service = OrderReconciliationMetricsService(
        enabled=True,
        batch_size=10,
        status_provider=lambda: build_status(
            last_action="FAILED",
            last_error="Binance unavailable.",
            failed_ticks=1,
        ),
    )

    metrics = service.render()

    assert (
        "signalai_order_reconciliation_"
        "last_tick_failed 1"
    ) in metrics
    assert (
        "signalai_order_reconciliation_"
        'last_action_info{action="FAILED"} 1'
    ) in metrics


def test_reconciliation_metrics_validate_batch_size(
) -> None:
    with pytest.raises(
        ValueError,
        match="batch size",
    ):
        OrderReconciliationMetricsService(
            enabled=True,
            batch_size=0,
            status_provider=build_status,
        )


def test_reconciliation_metrics_endpoint_contract(
) -> None:
    response = (
        get_order_reconciliation_metrics()
    )

    assert response.status_code == 200
    assert response.media_type.startswith(
        "text/plain"
    )

    body = response.body.decode("utf-8")

    assert (
        "signalai_order_reconciliation_enabled"
        in body
    )
    assert (
        "signalai_order_reconciliation_read_only 1"
        in body
    )


def test_reconciliation_metrics_route_registered(
) -> None:
    path = (
        "/api/v3/orders/reconciliation/metrics"
    )

    registered = [
        method
        for route in app.routes
        if route.path == path
        for method in getattr(
            route,
            "methods",
            set(),
        )
        if method == "GET"
    ]

    assert registered == ["GET"]
