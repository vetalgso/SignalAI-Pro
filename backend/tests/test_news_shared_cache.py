from __future__ import annotations

import asyncio

from app.news.service import NewsService


def test_concurrent_asset_queries_share_feed_fetches() -> None:
    NewsService._feed_cache = None
    NewsService._feed_load_task = None
    calls: list[str] = []
    service = NewsService()

    async def fake_fetch(
        source: str,
        url: str,
    ) -> list[dict[str, object]]:
        calls.append(url)
        await asyncio.sleep(0)
        return [
            {
                "id": source,
                "source": source,
                "title": source,
                "url": url,
                "summary": "",
                "published_at": "2026-09-02T00:00:00+00:00",
                "assets": ["BTC", "ETH"],
                "sentiment": "neutral",
                "impact_score": 35,
                "status": "unverified",
            }
        ]

    service._fetch = fake_fetch  # type: ignore[method-assign]

    async def run() -> tuple[dict[str, object], dict[str, object]]:
        btc, eth = await asyncio.gather(
            service.latest(asset="BTC"),
            service.latest(asset="ETH"),
        )
        return btc, eth

    btc, eth = asyncio.run(run())

    assert len(calls) == 3
    assert btc["count"] == 3
    assert eth["count"] == 3
