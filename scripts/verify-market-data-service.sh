#!/usr/bin/env bash
set -euo pipefail

docker compose exec -T api python - <<'PY'
import asyncio

from app.tradinggpt.data import MarketDataService


async def main() -> None:
    service = MarketDataService()

    snapshot = await service.get_market_snapshot(
        asset="BTC",
        interval="1h",
        candle_limit=250,
    )

    assert snapshot.asset == "BTC"
    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.interval == "1h"
    assert snapshot.price > 0
    assert len(snapshot.candles) >= 50
    assert snapshot.source == "binance"
    assert snapshot.data_quality > 0
    assert isinstance(snapshot.indicators, dict)

    print("MarketDataService verification passed")
    print(f"asset: {snapshot.asset}")
    print(f"symbol: {snapshot.symbol}")
    print(f"price: {snapshot.price}")
    print(f"candles: {len(snapshot.candles)}")
    print(f"volume_ratio: {snapshot.volume_ratio}")
    print(f"data_quality: {snapshot.data_quality}")
    print(f"source: {snapshot.source}")
    print(f"from_cache: {snapshot.from_cache}")
    print(
        "warnings:",
        [warning.model_dump() for warning in snapshot.warnings],
    )


asyncio.run(main())
PY
