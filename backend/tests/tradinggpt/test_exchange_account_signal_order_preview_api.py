from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.tradinggpt.exchange_accounts import (
    order_router as exchange_account_router,
)
from app.tradinggpt.orders.risk import (
    OrderRiskUsage,
    OrderRiskUsageUnavailableError,
)
from app.tradinggpt.orders.signal_order_orchestrator import (
    SignalOrderIneligibleError,
    SignalOrderNotFoundError,
)

from tests.tradinggpt.exchange_account_order_api_support import (
    FakeDb,
    FakeExchangeAccountService,
    FakeExecutionService,
    clear_auth_overrides,
    install_auth_overrides,
)


PATH = (
    "/api/v3/exchange/accounts/"
    "42/signals/77/orders/preview"
)


class FakePlan:
    def to_dict(
        self,
    ) -> dict[str, object]:
        return {
            "signal_id": 77,
            "signal_status": "ACTIVE",
            "strategy": "trend_momentum",
            "confidence": 82.5,
            "risk_level": "MEDIUM",
            "timeframe": "1h",
            "intent": {
                "exchange": "BINANCE",
                "market_type": "SPOT",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": 0.25,
                "reference_price": 101.0,
                "stop_loss": 95.0,
                "take_profit_1": 110.0,
                "take_profit_2": 115.0,
                "leverage": 1,
                "reduce_only": False,
            },
            "preview": {
                "exchange": "BINANCE",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "order_type": "LIMIT",
                "valid": True,
                "requested_quantity": 0.25,
                "normalized_quantity": 0.25,
                "requested_price": 101.0,
                "normalized_price": 101.0,
                "estimated_notional": 25.25,
                "available_balance": 1000.0,
                "balance_asset": "USDT",
                "errors": [],
                "warnings": [],
            },
        }


def install_account_service(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    FakeExchangeAccountService,
    FakeExecutionService,
]:
    execution = FakeExecutionService()
    account_service = (
        FakeExchangeAccountService(
            execution
        )
    )

    monkeypatch.setattr(
        exchange_account_router,
        "build_service",
        lambda _: account_service,
    )

    return account_service, execution


def test_signal_preview_requires_authentication(
    client: TestClient,
) -> None:
    clear_auth_overrides()

    response = client.post(
        PATH,
        json={"quantity": 0.25},
    )

    assert response.status_code == 401


def test_signal_preview_uses_owned_account_and_risk(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = FakeDb()
    account_service, execution = (
        install_account_service(
            monkeypatch
        )
    )

    signals = object()
    risk_policy = object()
    usage = OrderRiskUsage(
        daily_notional=10.0,
        open_orders=1,
    )

    repository_calls: list[object] = []
    usage_calls: list[
        dict[str, object]
    ] = []
    orchestrator_init: list[
        dict[str, object]
    ] = []
    preview_calls: list[
        dict[str, object]
    ] = []

    def repository_factory(
        selected_db: object,
    ) -> object:
        repository_calls.append(
            selected_db
        )
        return signals

    def risk_usage_factory(
        selected_db: object,
        **kwargs: object,
    ) -> OrderRiskUsage:
        usage_calls.append(
            {
                "db": selected_db,
                **kwargs,
            }
        )
        return usage

    class FakeOrchestrator:
        def __init__(
            self,
            **kwargs: object,
        ) -> None:
            orchestrator_init.append(
                kwargs
            )

        def preview(
            self,
            **kwargs: object,
        ) -> FakePlan:
            preview_calls.append(kwargs)
            return FakePlan()

    monkeypatch.setattr(
        exchange_account_router,
        "TradingSignalRepository",
        repository_factory,
    )
    monkeypatch.setattr(
        exchange_account_router,
        "build_order_risk_policy",
        lambda: risk_policy,
    )
    monkeypatch.setattr(
        exchange_account_router,
        "build_order_risk_usage",
        risk_usage_factory,
    )
    monkeypatch.setattr(
        exchange_account_router,
        "SignalToOrderOrchestrator",
        FakeOrchestrator,
    )

    install_auth_overrides(db)

    try:
        response = client.post(
            PATH,
            json={"quantity": 0.25},
        )
    finally:
        clear_auth_overrides()

    assert response.status_code == 200

    assert account_service.calls == [
        {
            "account_id": 42,
            "user_id": 7,
        }
    ]
    assert repository_calls == [db]

    assert usage_calls == [
        {
            "db": db,
            "execution_service": execution,
            "user_id": 7,
            "account_id": 42,
        }
    ]

    assert orchestrator_init == [
        {
            "signals": signals,
            "execution_service": execution,
            "risk_policy": risk_policy,
        }
    ]

    assert preview_calls == [
        {
            "signal_id": 77,
            "quantity": 0.25,
            "usage": usage,
        }
    ]

    payload = response.json()

    assert payload["account_id"] == 42
    assert payload["signal_id"] == 77
    assert payload["source"] == (
        "TRADINGGPT_SIGNAL"
    )
    assert payload["read_only"] is True
    assert payload["signal_status"] == "ACTIVE"
    assert payload["intent"]["side"] == "BUY"
    assert (
        payload["intent"]["order_type"]
        == "LIMIT"
    )
    assert payload["preview"]["valid"] is True
    assert (
        payload["preview"][
            "estimated_notional"
        ]
        == 25.25
    )

    assert execution.intent is None
    assert db.rollback_calls == 0


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (
            SignalOrderNotFoundError(
                "Trading signal was not found."
            ),
            404,
        ),
        (
            SignalOrderIneligibleError(
                "Trading signal has expired."
            ),
            409,
        ),
    ],
)
def test_signal_preview_maps_signal_errors(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status_code: int,
) -> None:
    db = FakeDb()
    install_account_service(monkeypatch)

    monkeypatch.setattr(
        exchange_account_router,
        "TradingSignalRepository",
        lambda _: object(),
    )
    monkeypatch.setattr(
        exchange_account_router,
        "build_order_risk_usage",
        lambda *args, **kwargs: (
            OrderRiskUsage()
        ),
    )

    class FailingOrchestrator:
        def __init__(
            self,
            **kwargs: object,
        ) -> None:
            pass

        def preview(
            self,
            **kwargs: object,
        ) -> FakePlan:
            raise error

    monkeypatch.setattr(
        exchange_account_router,
        "SignalToOrderOrchestrator",
        FailingOrchestrator,
    )

    install_auth_overrides(db)

    try:
        response = client.post(
            PATH,
            json={"quantity": 0.25},
        )
    finally:
        clear_auth_overrides()

    assert response.status_code == status_code
    assert response.json()["detail"] == str(error)
    assert db.rollback_calls == 1


def test_signal_preview_fails_closed_when_usage_unavailable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = FakeDb()
    install_account_service(monkeypatch)

    def unavailable(
        *args: object,
        **kwargs: object,
    ) -> OrderRiskUsage:
        raise OrderRiskUsageUnavailableError(
            "TESTNET usage unavailable."
        )

    monkeypatch.setattr(
        exchange_account_router,
        "build_order_risk_usage",
        unavailable,
    )

    install_auth_overrides(db)

    try:
        response = client.post(
            PATH,
            json={"quantity": 0.25},
        )
    finally:
        clear_auth_overrides()

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "TESTNET usage unavailable."
    )
    assert db.rollback_calls == 1


@pytest.mark.parametrize(
    "quantity",
    [
        0,
        -1,
    ],
)
def test_signal_preview_validates_quantity_before_route(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    quantity: float,
) -> None:
    db = FakeDb()
    account_service, _ = (
        install_account_service(
            monkeypatch
        )
    )

    install_auth_overrides(db)

    try:
        response = client.post(
            PATH,
            json={"quantity": quantity},
        )
    finally:
        clear_auth_overrides()

    assert response.status_code == 422
    assert account_service.calls == []
    assert db.rollback_calls == 0


def test_signal_preview_rejects_missing_quantity(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = FakeDb()
    account_service, _ = (
        install_account_service(
            monkeypatch
        )
    )

    install_auth_overrides(db)

    try:
        response = client.post(
            PATH,
            json={},
        )
    finally:
        clear_auth_overrides()

    assert response.status_code == 422
    assert account_service.calls == []
    assert db.rollback_calls == 0
