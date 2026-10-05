from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_paper_portfolio_snapshot_endpoint() -> None:
    response = client.get(
        "/api/v3/portfolio/snapshot"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["source"] == "PAPER"
    assert payload["balances"] == []
    assert payload["open_orders"] == []
    assert payload["positions"] == []
    assert payload["total_wallet_balance"] == 0.0
    assert payload["captured_at"]


def test_portfolio_snapshot_rejects_unknown_source() -> None:
    response = client.get(
        "/api/v3/portfolio/snapshot",
        params={"source": "UNKNOWN"},
    )

    assert response.status_code == 400
    assert (
        "Unsupported portfolio source"
        in response.json()["detail"]
    )


def test_portfolio_route_is_registered() -> None:
    paths = {
        route.path
        for route in app.routes
    }

    assert "/api/v3/portfolio/snapshot" in paths
