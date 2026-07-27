from __future__ import annotations

from fastapi.testclient import TestClient


def build_payload(
    *,
    exchange: str = "PAPER",
    order_type: str = "MARKET",
) -> dict[str, object]:
    return {
        "exchange": exchange,
        "market_type": "SPOT",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "order_type": order_type,
        "quantity": 0.01,
        "reference_price": 100_000.0,
        "stop_loss": 98_500.0,
        "take_profit_1": 102_000.0,
        "take_profit_2": 104_000.0,
        "leverage": 1,
        "reduce_only": False,
    }


def test_paper_market_order_endpoint_returns_filled(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v3/orders/execute",
        json=build_payload(),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["exchange"] == "PAPER"
    assert payload["symbol"] == "BTCUSDT"
    assert payload["status"] == "FILLED"
    assert payload["filled_quantity"] == 0.01
    assert payload["average_price"] == 100_000.0
    assert payload["simulated"] is True


def test_paper_limit_order_endpoint_returns_open(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v3/orders/execute",
        json=build_payload(order_type="LIMIT"),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "OPEN"
    assert payload["filled_quantity"] == 0.0
    assert payload["average_price"] is None


def test_order_endpoint_rejects_invalid_quantity(
    client: TestClient,
) -> None:
    payload = build_payload()
    payload["quantity"] = 0

    response = client.post(
        "/api/v3/orders/execute",
        json=payload,
    )

    assert response.status_code == 422


def test_order_endpoint_rejects_spot_leverage(
    client: TestClient,
) -> None:
    payload = build_payload()
    payload["leverage"] = 3

    response = client.post(
        "/api/v3/orders/execute",
        json=payload,
    )

    assert response.status_code == 422


def test_order_endpoint_rejects_unregistered_exchange(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v3/orders/execute",
        json=build_payload(exchange="BINANCE"),
    )

    assert response.status_code == 400
    assert "BINANCE" in response.json()["detail"]


def test_order_execution_route_is_registered(
    client: TestClient,
) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]

    assert "/api/v3/orders/execute" in paths
    assert "post" in paths["/api/v3/orders/execute"]
