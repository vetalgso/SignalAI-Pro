#!/usr/bin/env bash

set -euo pipefail

docker compose exec -T api python - <<'PY'
import asyncio

from pydantic import ValidationError

from app.tradinggpt.orchestrator import (
    TradingGPTOrchestrator,
)
from app.tradinggpt.schemas import (
    AssistantChatRequest,
    InvestorContext,
)


def verify_context_validation() -> None:
    context = InvestorContext(
        existing_assets=[
            "BTC",
            "btc",
            " ETH ",
        ],
        current_allocations={
            "BTC": 40,
            "DOGE": 15,
        },
    )

    assert context.existing_assets == [
        "BTC",
        "ETH",
        "DOGE",
    ]

    assert context.current_allocations == {
        "BTC": 40.0,
        "DOGE": 15.0,
    }

    try:
        InvestorContext(
            current_allocations={
                "BTC": 70,
                "ETH": 40,
            },
        )
    except ValidationError:
        pass
    else:
        raise AssertionError(
            "Allocation total above 100 was accepted"
        )

    try:
        InvestorContext(
            current_allocations={
                "BTC": -1,
            },
        )
    except ValidationError:
        pass
    else:
        raise AssertionError(
            "Negative allocation was accepted"
        )


async def verify_rebalancing() -> None:
    request = AssistantChatRequest(
        message=(
            "Проанализируй мой портфель и "
            "предложи ребалансировку"
        ),
        context=InvestorContext(
            capital=20_000,
            currency="USD",
            risk_level="medium",
            investment_horizon="medium",
            max_position_percent=25,
            current_allocations={
                "BTC": 40,
                "ETH": 20,
                "Cash / USD": 25,
                "DOGE": 15,
            },
        ),
    )

    response = await TradingGPTOrchestrator().chat(
        request
    )

    assert response.intent == "portfolio_allocation"
    assert response.portfolio

    positions = {
        item.asset: item
        for item in response.portfolio
    }

    assert positions["BTC"].allocation_percent == 25
    assert positions["BTC"].amount == 5000
    assert positions["BTC"].reason.startswith(
        "[REDUCE]"
    )

    assert positions["ETH"].allocation_percent == 20
    assert positions["ETH"].amount == 4000
    assert positions["ETH"].reason.startswith(
        "[HOLD]"
    )

    assert (
        positions["NASDAQ ETF"].allocation_percent
        == 20
    )
    assert positions["NASDAQ ETF"].reason.startswith(
        "[ADD]"
    )

    assert positions["Gold"].allocation_percent == 15
    assert positions["Gold"].reason.startswith(
        "[ADD]"
    )

    assert (
        positions["S&P 500 ETF"].allocation_percent
        == 10
    )
    assert positions[
        "S&P 500 ETF"
    ].reason.startswith("[ADD]")

    assert (
        positions["Cash / USD"].allocation_percent
        == 10
    )
    assert positions[
        "Cash / USD"
    ].reason.startswith("[REDUCE]")

    assert positions["DOGE"].allocation_percent == 0
    assert positions["DOGE"].amount == 0
    assert positions["DOGE"].reason.startswith(
        "[AVOID]"
    )

    engine_positions = {
        item["asset"]: item
        for item in response.details[
            "portfolio"
        ]["positions"]
    }

    assert engine_positions["BTC"]["action"] == (
        "REDUCE"
    )
    assert engine_positions["ETH"]["action"] == (
        "HOLD"
    )
    assert engine_positions["DOGE"]["action"] == (
        "AVOID"
    )

    total = sum(
        item.allocation_percent
        for item in response.portfolio
    )

    assert abs(total - 100.0) < 0.000001

    print(
        "TradingGPT Portfolio Rebalancing "
        "verification passed"
    )

    print(response.answer)

    print(
        [
            {
                "asset": item.asset,
                "target_percent": (
                    item.allocation_percent
                ),
                "amount": item.amount,
                "action": item.reason.split(
                    "]",
                    maxsplit=1,
                )[0].removeprefix("["),
            }
            for item in response.portfolio
        ]
    )


verify_context_validation()
asyncio.run(verify_rebalancing())
PY
