from __future__ import annotations
import asyncio
import hashlib
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree
import httpx

FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("Decrypt", "https://decrypt.co/feed"),
]
ASSETS = {
    "BTC": ["bitcoin", "btc"], "ETH": ["ethereum", "ether", "eth"], "BNB": ["bnb", "binance coin"],
    "SOL": ["solana", "sol"], "XRP": ["xrp", "ripple"], "ADA": ["cardano", "ada"],
    "DOGE": ["dogecoin", "doge"], "TRX": ["tron", "trx"], "AVAX": ["avalanche", "avax"], "LINK": ["chainlink", "link"],
}
POSITIVE = {"approve", "approval", "adoption", "launch", "upgrade", "partnership", "surge", "gain", "record", "inflow", "bullish"}
NEGATIVE = {"hack", "exploit", "lawsuit", "ban", "outflow", "crash", "fraud", "liquidation", "bearish", "breach", "shutdown"}

class NewsService:
    CACHE_TTL_SECONDS = 60.0
    _feed_cache: tuple[
        float,
        list[dict[str, Any]],
        list[str],
    ] | None = None
    _feed_load_task: asyncio.Task[
        tuple[list[dict[str, Any]], list[str]]
    ] | None = None

    async def latest(self, limit: int = 50, asset: str | None = None) -> dict[str, Any]:
        articles, errors = await self._all_articles()

        articles = list(articles)

        if asset:
            wanted = asset.upper()
            articles = [a for a in articles if wanted in a["assets"]]

        return {
            "count": len(articles[:limit]),
            "partial": bool(errors),
            "articles": articles[:limit],
        }

    async def _all_articles(
        self,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        cached = self.__class__._feed_cache
        now = time.monotonic()

        if cached is not None and now < cached[0]:
            return cached[1], cached[2]

        task = self.__class__._feed_load_task

        if task is None or task.done():
            task = asyncio.create_task(
                self._fetch_all_articles()
            )
            self.__class__._feed_load_task = task

        try:
            articles, errors = await asyncio.shield(task)
        finally:
            if task.done() and self.__class__._feed_load_task is task:
                self.__class__._feed_load_task = None

        self.__class__._feed_cache = (
            time.monotonic() + self.CACHE_TTL_SECONDS,
            articles,
            errors,
        )

        return articles, errors

    async def _fetch_all_articles(
        self,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        results = await asyncio.gather(*(self._fetch(name, url) for name, url in FEEDS), return_exceptions=True)
        articles: list[dict[str, Any]] = []
        errors: list[str] = []
        for result in results:
            if isinstance(result, Exception):
                errors.append(type(result).__name__)
            else:
                articles.extend(result)
        unique = {a["id"]: a for a in articles}
        articles = sorted(unique.values(), key=lambda x: x["published_at"], reverse=True)
        return articles, errors

    async def _fetch(self, source: str, url: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=8, headers={"User-Agent": "SignalAI-Pro/2.0"}, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        items = root.findall(".//item")[:30]
        out = []
        for item in items:
            title = self._text(item, "title")
            link = self._text(item, "link")
            description = re.sub("<[^>]+>", " ", self._text(item, "description"))
            text = f"{title} {description}".lower()
            assets = [symbol for symbol, keys in ASSETS.items() if any(re.search(rf"\b{re.escape(k)}\b", text) for k in keys)]
            tokens = set(re.findall(r"[a-z]+", text))
            pos, neg = len(tokens & POSITIVE), len(tokens & NEGATIVE)
            sentiment = "positive" if pos > neg else "negative" if neg > pos else "neutral"
            impact = min(100, 35 + 10 * len(assets) + 12 * abs(pos - neg) + (10 if source == "CoinDesk" else 5))
            published = self._date(self._text(item, "pubDate"))
            out.append({"id": hashlib.sha1((title + link).encode()).hexdigest()[:16], "source": source, "title": title, "url": link, "summary": description[:300].strip(), "published_at": published, "assets": assets, "sentiment": sentiment, "impact_score": impact, "status": "unverified"})
        return out

    @staticmethod
    def _text(item: Any, tag: str) -> str:
        node = item.find(tag)
        return (node.text or "").strip() if node is not None else ""

    @staticmethod
    def _date(value: str) -> str:
        try:
            dt = parsedate_to_datetime(value)
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except Exception:
            return datetime.now(timezone.utc).isoformat()
