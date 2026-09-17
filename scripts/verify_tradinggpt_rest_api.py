from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


URL = "http://localhost:8000/api/v3/engine/analyze"


def build_payload() -> dict[str, object]:
    return {
        "scoring": {
            "score": 82.0,
            "opportunity_score": 85.0,
            "consensus_score": 70.0,
            "confidence": 90,
            "trade_direction": "LONG",
            "signal_score": 80.0,
            "forecast_score": 84.0,
            "news_score": 76.0,
        },
        "market_regime": {
            "market_regime": "RISK_ON",
            "confidence": 0.88,
            "trend_regime": "BULL",
            "risk_environment": "RISK_ON",
            "risk_asset_score": 78.0,
            "defensive_asset_score": 22.0,
            "risk_appetite_score": 75.0,
            "market_breadth_score": 0.72,
            "volatility_score": 35.0,
            "signals": [],
            "reasons": [
                "Risk assets are broadly supported."
            ],
            "warnings": [],
        },
        "portfolio": {
            "capital": 10000.0,
            "currency": "USD",
            "risk_level": "medium",
            "max_position_percent": 25.0,
            "max_risk_per_trade_percent": 1.0,
            "portfolio_risk_score": 30.0,
            "cash_reserve_percent": 20.0,
            "invested_percent": 80.0,
            "positions": [],
            "trades": [],
            "min_trade_amount": 25.0,
            "trading_fee_percent": 0.1,
            "rebalance_tolerance_percent": 0.5,
            "trade_rounding_amount": 1.0,
            "estimated_total_fees": 0.0,
            "warnings": [],
        },
    }


def request_analysis() -> dict[str, object]:
    request = Request(
        URL,
        data=json.dumps(build_payload()).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            assert response.status == 200
            return json.loads(
                response.read().decode("utf-8")
            )
    except HTTPError as error:
        body = error.read().decode(
            "utf-8",
            errors="replace",
        )
        raise AssertionError(
            f"API returned HTTP {error.code}: {body}"
        ) from error
    except URLError as error:
        raise AssertionError(
            f"TradingGPT API is unavailable at {URL}: "
            f"{error}"
        ) from error


def main() -> None:
    payload = request_analysis()

    conviction = payload["conviction"]

    assert conviction["score"] == 76.5
    assert conviction["level"] == "HIGH"
    assert conviction["recommendation"] == "BUY"
    assert conviction["confidence"] == 0.765
    assert conviction["position_multiplier"] == 1.25

    assert conviction["factors"] == {
        "signal_score": 80.0,
        "market_score": 75.0,
        "portfolio_score": 70.0,
        "quality_score": 80.0,
    }

    assert "scoring" in payload
    assert "market_regime" in payload
    assert "portfolio" in payload
    assert "explanation" in payload

    print(json.dumps(conviction, indent=2))
    print("TradingGPT REST API verification passed")


if __name__ == "__main__":
    main()
