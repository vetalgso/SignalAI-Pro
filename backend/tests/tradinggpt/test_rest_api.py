from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def test_analysis_endpoint_returns_expected_result(
    client: TestClient,
    analysis_payload: dict[str, Any],
) -> None:
    response = client.post(
        "/api/v3/engine/analyze",
        json=analysis_payload,
    )

    assert response.status_code == 200

    payload = response.json()
    conviction = payload["conviction"]

    assert conviction["score"] == 76.5
    assert conviction["level"] == "HIGH"
    assert conviction["recommendation"] == "BUY"
    assert conviction["confidence"] == 0.765
    assert conviction["position_multiplier"] == 1.25

    explanation = payload["explanation"]

    assert explanation["risk_level"] == "MEDIUM"
    assert explanation["pros"]
    assert explanation["risks"]


def test_tradinggpt_routes_are_registered(
    client: TestClient,
) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]

    assert "/api/v3/assistant/chat" in paths
    assert "/api/v3/assistant/market-scan" in paths
    assert "/api/v3/engine/analyze" in paths

    assert "post" in paths["/api/v3/assistant/chat"]
    assert "post" in paths["/api/v3/assistant/market-scan"]
    assert "post" in paths["/api/v3/engine/analyze"]
