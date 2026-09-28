#!/usr/bin/env bash

set -euo pipefail

docker compose exec -T api python - <<'PY'
import asyncio

from app.tradinggpt.orchestrator import (
    TradingGPTOrchestrator,
)
from app.tradinggpt.portfolio import PortfolioEngine
from app.tradinggpt.schemas import (
    AssistantChatRequest,
    InvestorContext,
)


def verify_execution_constraints() -> None:
    result = PortfolioEngine.build(
        risk_level="medium",
        capital=20_000,
        currency="USD",
        current_allocations={
            "BTC": 40,
            "ETH": 20,
            "Cash / USD": 25,
            "DOGE": 15,
        },
        min_trade_amount=25,
        trading_fee_percent=0.1,
        rebalance_tolerance_percent=0.5,
        trade_rounding_amount=10,
    )

    trades = {
        trade.asset: trade
        for trade in result.trades
    }

    assert trades["BTC"].action == "SELL"
    assert trades["BTC"].trade_amount == 3000
    assert trades["BTC"].estimated_fee == 3
    assert trades["BTC"].net_cash_flow == 2997

    assert trades["NASDAQ ETF"].action == "BUY"
    assert trades["NASDAQ ETF"].trade_amount == 4000
    assert trades["NASDAQ ETF"].estimated_fee == 4
    assert trades["NASDAQ ETF"].net_cash_flow == -4004

    assert trades["DOGE"].action == "EXIT"
    assert trades["DOGE"].trade_amount == 3000
    assert trades["DOGE"].estimated_fee == 3
    assert trades["DOGE"].net_cash_flow == 2997

    assert result.estimated_total_fees == 18

    serialized = result.to_dict()

    assert serialized["execution"] == {
        "min_trade_amount": 25,
        "trading_fee_percent": 0.1,
        "rebalance_tolerance_percent": 0.5,
        "trade_rounding_amount": 10,
        "estimated_total_fees": 18,
    }


def verify_tolerance_and_minimum() -> None:
    tolerance_result = PortfolioEngine.build(
        risk_level="medium",
        capital=10_000,
        current_allocations={
            "BTC": 24.7,
            "ETH": 20,
            "NASDAQ ETF": 20,
            "Gold": 15,
            "S&P 500 ETF": 10,
            "Cash / USD": 10.3,
        },
        rebalance_tolerance_percent=0.5,
    )

    tolerance_trades = {
        trade.asset: trade
        for trade in tolerance_result.trades
    }

    assert tolerance_trades["BTC"].action == "HOLD"
    assert tolerance_trades["BTC"].trade_amount == 0

    minimum_result = PortfolioEngine.build(
        risk_level="medium",
        capital=1_000,
        current_allocations={
            "BTC": 23,
            "ETH": 20,
            "NASDAQ ETF": 20,
            "Gold": 15,
            "S&P 500 ETF": 10,
            "Cash / USD": 12,
        },
        min_trade_amount=25,
        rebalance_tolerance_percent=0,
        trade_rounding_amount=1,
    )

    minimum_trades = {
        trade.asset: trade
        for trade in minimum_result.trades
    }

    assert minimum_trades["BTC"].action == "HOLD"
    assert minimum_trades["BTC"].trade_amount == 0
    assert "ниже минимального лимита" in (
        minimum_trades["BTC"].reason
    )


async def verify_orchestrator() -> None:
    response = await TradingGPTOrchestrator().chat(
        AssistantChatRequest(
            message=(
                "Составь исполнимый план "
                "ребалансировки с комиссиями"
            ),
            context=InvestorContext(
                capital=20_000,
                currency="USD",
                risk_level="medium",
                current_allocations={
                    "BTC": 40,
                    "ETH": 20,
                    "Cash / USD": 25,
                    "DOGE": 15,
                },
                min_trade_amount=25,
                trading_fee_percent=0.1,
                rebalance_tolerance_percent=0.5,
                trade_rounding_amount=10,
            ),
        )
    )

    execution = response.details["execution"]

    assert execution["estimated_total_fees"] == 18
    assert execution["min_trade_amount"] == 25
    assert execution["trade_rounding_amount"] == 10

    btc = next(
        trade
        for trade in response.details["trade_plan"]
        if trade["asset"] == "BTC"
    )

    assert btc["action"] == "SELL"
    assert btc["estimated_fee"] == 3
    assert btc["net_cash_flow"] == 2997

    assert (
        response.details["portfolio"]["execution"]
        == execution
    )

    print(
        "TradingGPT Portfolio Execution "
        "verification passed"
    )
    print(execution)


verify_execution_constraints()
verify_tolerance_and_minimum()
asyncio.run(verify_orchestrator())
PY
