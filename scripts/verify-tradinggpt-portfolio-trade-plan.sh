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


def verify_engine_trade_plan() -> None:
    result = PortfolioEngine.build(
        risk_level="medium",
        capital=20_000,
        currency="USD",
        max_position_percent=25,
        current_allocations={
            "BTC": 40,
            "ETH": 20,
            "Cash / USD": 25,
            "DOGE": 15,
        },
    )

    trades = {
        trade.asset: trade
        for trade in result.trades
    }

    btc = trades["BTC"]
    assert btc.action == "SELL"
    assert btc.current_percent == 40
    assert btc.target_percent == 25
    assert btc.delta_percent == -15
    assert btc.current_amount == 8000
    assert btc.target_amount == 5000
    assert btc.trade_amount == 3000

    eth = trades["ETH"]
    assert eth.action == "HOLD"
    assert eth.delta_percent == 0
    assert eth.trade_amount == 0

    nasdaq = trades["NASDAQ ETF"]
    assert nasdaq.action == "BUY"
    assert nasdaq.current_percent == 0
    assert nasdaq.target_percent == 20
    assert nasdaq.trade_amount == 4000

    gold = trades["Gold"]
    assert gold.action == "BUY"
    assert gold.trade_amount == 3000

    sp500 = trades["S&P 500 ETF"]
    assert sp500.action == "BUY"
    assert sp500.trade_amount == 2000

    cash = trades["Cash / USD"]
    assert cash.action == "SELL"
    assert cash.current_percent == 25
    assert cash.target_percent == 10
    assert cash.trade_amount == 3000

    doge = trades["DOGE"]
    assert doge.action == "EXIT"
    assert doge.current_percent == 15
    assert doge.target_percent == 0
    assert doge.current_amount == 3000
    assert doge.target_amount == 0
    assert doge.trade_amount == 3000

    serialized = result.to_dict()

    assert "trades" in serialized
    assert len(serialized["trades"]) == 7

    trade_total_buy = sum(
        trade.trade_amount or 0
        for trade in result.trades
        if trade.action == "BUY"
    )

    trade_total_sell = sum(
        trade.trade_amount or 0
        for trade in result.trades
        if trade.action in {"SELL", "EXIT"}
    )

    assert trade_total_buy == 9000
    assert trade_total_sell == 9000


async def verify_orchestrator_trade_plan() -> None:
    request = AssistantChatRequest(
        message=(
            "Составь конкретный план сделок "
            "для ребалансировки портфеля"
        ),
        context=InvestorContext(
            capital=20_000,
            currency="USD",
            risk_level="medium",
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

    trade_plan = response.details["trade_plan"]

    trades = {
        trade["asset"]: trade
        for trade in trade_plan
    }

    assert trades["BTC"]["action"] == "SELL"
    assert trades["BTC"]["trade_amount"] == 3000

    assert trades["ETH"]["action"] == "HOLD"
    assert trades["ETH"]["trade_amount"] == 0

    assert (
        trades["NASDAQ ETF"]["action"]
        == "BUY"
    )
    assert (
        trades["NASDAQ ETF"]["trade_amount"]
        == 4000
    )

    assert trades["Gold"]["action"] == "BUY"
    assert trades["Gold"]["trade_amount"] == 3000

    assert (
        trades["S&P 500 ETF"]["action"]
        == "BUY"
    )
    assert (
        trades["S&P 500 ETF"]["trade_amount"]
        == 2000
    )

    assert (
        trades["Cash / USD"]["action"]
        == "SELL"
    )
    assert (
        trades["Cash / USD"]["trade_amount"]
        == 3000
    )

    assert trades["DOGE"]["action"] == "EXIT"
    assert trades["DOGE"]["trade_amount"] == 3000

    assert (
        response.details["portfolio"]["trades"]
        == trade_plan
    )

    assert (
        "Для ребалансировки требуется 6 операций."
        in response.answer
    )

    print(
        "TradingGPT Portfolio Trade Plan "
        "verification passed"
    )

    for trade in trade_plan:
        print(
            trade["action"],
            trade["asset"],
            trade["trade_amount"],
            trade["currency"],
            "|",
            trade["reason"],
        )


verify_engine_trade_plan()
asyncio.run(verify_orchestrator_trade_plan())
PY
