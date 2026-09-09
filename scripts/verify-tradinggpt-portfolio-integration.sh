#!/usr/bin/env bash

set -euo pipefail

docker compose exec -T api python - <<'PY'
import asyncio

from app.tradinggpt.orchestrator import (
    TradingGPTOrchestrator,
)
from app.tradinggpt.schemas import (
    AssistantChatRequest,
    InvestorContext,
)


async def main() -> None:
    request = AssistantChatRequest(
        message="Как распределить мой инвестиционный портфель?",
        context=InvestorContext(
            capital=10_000,
            currency="USD",
            risk_level="high",
            investment_horizon="medium",
            existing_assets=[
                "BTC",
                "DOGE",
            ],
            max_position_percent=20,
        ),
    )

    response = await TradingGPTOrchestrator().chat(
        request
    )

    assert response.intent == "portfolio_allocation"
    assert response.confidence == 82
    assert response.portfolio

    details = response.details

    required_details = {
        "portfolio_risk_score",
        "cash_reserve_percent",
        "invested_percent",
        "max_position_percent",
        "max_risk_per_trade_percent",
        "warnings",
        "portfolio",
    }

    assert required_details <= details.keys()

    assert details["max_position_percent"] == 20
    assert details["max_risk_per_trade_percent"] == 2.0
    assert details["cash_reserve_percent"] == 25.0
    assert details["invested_percent"] == 75.0
    assert details["warnings"]

    allocations = {
        item.asset: item
        for item in response.portfolio
    }

    assert allocations["BTC"].allocation_percent == 20
    assert allocations["ETH"].allocation_percent == 20
    assert allocations["Cash / USD"].allocation_percent == 25

    assert allocations["BTC"].reason.startswith(
        "[ADD]"
    )
    assert allocations["DOGE"].reason.startswith(
        "[AVOID]"
    )

    total = sum(
        item.allocation_percent
        for item in response.portfolio
    )

    assert abs(total - 100.0) < 0.000001

    assert "Риск портфеля:" in response.answer
    assert "Максимальный риск на одну сделку:" in (
        response.answer
    )
    assert "Денежный резерв:" in response.answer

    factor_types = {
        factor.type
        for factor in response.factors
    }

    assert {
        "portfolio_risk",
        "liquidity",
        "position_limit",
        "personalization",
    } <= factor_types

    print(
        "TradingGPT Portfolio Integration "
        "verification passed"
    )
    print(response.answer)
    print(details)
    print(
        [
            {
                "asset": item.asset,
                "allocation": item.allocation_percent,
                "amount": item.amount,
                "reason": item.reason,
            }
            for item in response.portfolio
        ]
    )


asyncio.run(main())
PY
