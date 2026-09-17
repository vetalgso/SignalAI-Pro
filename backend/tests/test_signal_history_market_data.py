import asyncio
from datetime import datetime, timezone

import pytest

from app.services.binance_market import BinanceMarketService
from app.tradinggpt.data.binance_provider import BinanceMarketDataProvider
from app.tradinggpt.data.service import MarketDataService


def test_history_page_uses_explicit_utc_bounds_without_snapshot_cache(monkeypatch):
    service = BinanceMarketService()
    calls = []
    async def get(path, params):
        calls.append((path, params))
        return [[0, "100", "101", "99", "100", "1", 59999, "100", 1, "0", "0", "0"]]
    monkeypatch.setattr(service, "_get", get)
    market = MarketDataService(provider=BinanceMarketDataProvider(service))
    async def forbidden(*args, **kwargs):
        raise AssertionError("History must not use a latest snapshot or its cache")
    monkeypatch.setattr(market, "_load_cached_snapshot", forbidden)
    page = asyncio.run(market.get_candle_history(
        asset="btcusdt", start_at=datetime(1970, 1, 1, tzinfo=timezone.utc),
        end_at=datetime(1970, 1, 1, 0, 1, tzinfo=timezone.utc), limit=1,
    ))
    assert calls == [("/api/v3/klines", {"symbol": "BTCUSDT", "interval": "1m",
                                      "limit": 1, "startTime": 0, "endTime": 59999})]
    assert page[0]["open_time"] == 0 and page[0]["close_time"] == 59999
    # Existing snapshot consumers retain the original three parameters.
    asyncio.run(service.klines("ETHUSDT", "1h", 250))
    assert calls[-1][1] == {"symbol": "ETHUSDT", "interval": "1h", "limit": 250}


def test_history_timeout_does_not_return_latest_data():
    class SlowProvider:
        async def get_candle_history(self, **kwargs):
            await asyncio.Event().wait()
    market = MarketDataService(provider=SlowProvider(), timeout_seconds=0.01)
    with pytest.raises(TimeoutError):
        asyncio.run(market.get_candle_history(
            asset="BTCUSDT", start_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_at=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc), limit=1,
        ))
