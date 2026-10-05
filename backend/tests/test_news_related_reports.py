import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from html import escape

import httpx
import pytest

from app.news.related_reports import annotate_related_reports, canonical_url
from app.news.service import NewsService

HTTP_CLIENT = httpx.AsyncClient
from app.tradinggpt.quality_guard import AnalysisQualityGuard

@pytest.fixture(autouse=True)
def isolated_http_client(monkeypatch):
    # RSS requests below are mocked; host proxy settings are irrelevant.
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(trust_env=False, **kwargs))


NOW = datetime(2026, 9, 22, 18, 0, tzinfo=timezone.utc)
ETF = [
    "Bitcoin ETFs Take Nearly $1B in a Day as Average Holder Returns to Profit",
    "Spot bitcoin ETFs attracted nearly $1 billion on Monday, the 9th largest inflow ever",
    "Bitcoin ETFs flirt with $1B as inflows hit 2026 high",
]
RECOVERY = [
    "White hats outrun Coldcard hackers in 52-Bitcoin evacuation",
    "Whitehats move 52 bitcoin from the Coldcard hack to a recovery trust",
]


def article(title, source="CoinDesk", **overrides):
    domain = {"CoinDesk": "coindesk.com", "Cointelegraph": "cointelegraph.com", "Decrypt": "decrypt.co"}[source]
    return {"id": source + title, "title": title, "source": source, "url": f"https://{domain}/news/story",
            "published_at": (NOW - timedelta(hours=2)).isoformat(), "published_at_source": "RSS",
            "assets": ["BTC"], "status": "unverified", "sentiment": "positive", "impact_score": 50, **overrides}


def linked(first, second):
    return annotate_related_reports([first, second], now=NOW)[0]["related_coverage"]["reports"]


def test_user_etf_examples_link_three_publishers_without_verifying_or_mutating():
    items = [article(title, source) for title, source in zip(ETF, ["Decrypt", "CoinDesk", "Cointelegraph"])]
    original = deepcopy(items)
    result = annotate_related_reports(items, now=NOW)
    assert all(row["related_coverage"]["other_publishers_count"] == 2 for row in result)
    assert all(row["status"] == "unverified" for row in result)
    assert AnalysisQualityGuard.news_verification_penalty({"articles": result}) == 10
    assert items == original
    assert result[0]["related_coverage"]["reports"][0]["basis"]["amount"] == "1000000000"


def test_recovery_requires_amount_asset_and_specific_shared_term():
    reports = linked(article(RECOVERY[0]), article(RECOVERY[1], "Cointelegraph"))
    assert reports[0]["basis"] == {"family": "ASSET_RECOVERY", "asset": "BTC", "amount": "52",
                                   "unit": "BTC", "direction": "RECOVERY", "shared_terms": ["coldcard"]}


@pytest.mark.parametrize("title", [
    "Bitcoin ETFs lose $1B in outflows", "Bitcoin ETFs take $2B in a day",
    "Ethereum ETFs take $1B in a day", "Bitcoin and Ethereum ETFs take $1B in a day",
    "Bitcoin ETFs could take $1B in a day", "Bitcoin ETFs will take $1B in a day",
    "Bitcoin ETFs did not take $1B in a day", "False: Bitcoin ETFs take $1B",
    "Correction: Bitcoin ETFs take $1B", "Bitcoin ETFs take $1B?",
    "Bitcoin price hits $1B", "Bitcoin ETFs take $1B and lose $1B",
    "Bitcoin ETFs take $1B and $2B", "Bitcoin ETFs take €1B in a day",
    "Bitcoin ETFs take $1B in weekly inflows", "Bitcoin ETF options attract $1B",
    "Bitcoin ETF fees take $1B in a day",
])
def test_different_contradictory_speculative_or_ambiguous_titles_do_not_link(title):
    assert not linked(article(ETF[0]), article(title, "Cointelegraph"))


@pytest.mark.parametrize("title", [
    RECOVERY[1].replace("52", "53"), RECOVERY[1].replace("Coldcard", "Otherwallet"),
    RECOVERY[1].replace("bitcoin", "ethereum"), "Hackers steal 52 bitcoin from Coldcard",
    "Whitehats could recover 52 bitcoin from the Coldcard hack",
])
def test_recovery_does_not_link_different_incidents_or_amounts(title):
    assert not linked(article(RECOVERY[0]), article(title, "Cointelegraph"))


@pytest.mark.parametrize("overrides", [
    {"published_at": (NOW - timedelta(hours=25)).isoformat()},
    {"published_at": (NOW + timedelta(minutes=1)).isoformat()},
    {"published_at": "invalid"}, {"published_at": "2026-09-22T16:00:00"},
    {"published_at_source": "FALLBACK"}, {"published_at_source": None},
    {"url": "javascript:alert(1)"}, {"url": "https://evil.test/story"},
    {"url": "https://cointelegraph.com.evil.test/story"},
    {"url": "https://user:pass@cointelegraph.com/story"},
])
def test_date_and_publisher_provenance_required(overrides):
    assert not linked(article(ETF[0]), article(ETF[1], "Cointelegraph", **overrides))


def test_no_same_publisher_inflation_no_transitive_grouping_and_weekday_conflicts():
    assert not linked(article(ETF[0]), article(ETF[1]))
    a = article(ETF[0] + " Monday", "Decrypt")
    b = article(ETF[1].replace("Monday", "Tuesday"))
    bridge = article(ETF[2], "Cointelegraph")
    rows = annotate_related_reports([a, b, bridge], now=NOW)
    assert [r["related_coverage"]["other_publishers_count"] for r in rows] == [1, 1, 2]


def test_tracking_duplicates_count_as_one_report_and_publisher():
    source = article(ETF[0], "Decrypt")
    other = article(ETF[1])
    duplicate = {**other, "url": other["url"] + "?utm_source=rss#top"}
    rows = annotate_related_reports([source, other, duplicate], now=NOW)
    assert len(rows[0]["related_coverage"]["reports"]) == 1
    assert rows[0]["related_coverage"]["other_publishers_count"] == 1
    assert canonical_url("CoinDesk", "http://www.coindesk.com/story/?utm_medium=rss&x=1") == "https://coindesk.com/story?x=1"


def test_unrelated_btc_titles_do_not_link():
    titles = ["Bitcoin price seeks $86K as new support after oil dips below $90",
              "Big Questions: Does Satoshi actually own 1.1 million Bitcoin?",
              "Bitcoin ETFs Take Nearly $1B in a Day as Average Holder Returns to Profit",
              "Crypto market cap reclaims $3 trillion as Bitcoin, altcoins rally"]
    rows = annotate_related_reports([article(title, source) for title, source in zip(
        titles, ["CoinDesk", "Decrypt", "Cointelegraph", "CoinDesk"])], now=NOW)
    assert all(not r["related_coverage"]["reports"] for r in rows)


def test_rss_to_api_matches_before_limit_and_keeps_quality_penalty(monkeypatch):
    # Use current time so the live API age check does not turn fixture ages stale.
    now = datetime.now(timezone.utc)
    async def fake_get(self, url):
        index = 0 if "decrypt" in url else 1 if "coindesk" in url else 2
        domain = ["decrypt.co", "coindesk.com", "cointelegraph.com"][index]
        date = (now - timedelta(hours=index + 1)).strftime('%a, %d %b %Y %H:%M:%S +0000')
        xml = f'<rss><channel><item><title>{escape(ETF[index])}</title><link>https://{domain}/story</link><pubDate>{date}</pubDate></item></channel></rss>'
        return httpx.Response(200, content=xml.encode(), request=httpx.Request('GET', url))
    monkeypatch.setattr(HTTP_CLIENT, "get", fake_get)
    monkeypatch.setattr(NewsService, "_feed_cache", None)
    monkeypatch.setattr(NewsService, "_feed_load_task", None)
    page = asyncio.run(NewsService().latest(asset="BTC", limit=1))
    assert page["count"] == 1
    assert page["articles"][0]["related_coverage"]["other_publishers_count"] == 2
    assert page["articles"][0]["published_at_source"] == "RSS"
    assert AnalysisQualityGuard.news_verification_penalty(page) == 10


@pytest.mark.parametrize("date", ["", "bad date", "Tue, 22 Sep 2026 16:00:00 -0000"])
def test_rss_fallback_dates_are_not_treated_as_fresh_evidence(monkeypatch, date):
    async def fake_get(self, url):
        xml = f'<rss><channel><item><title>{escape(ETF[0])}</title><link>https://decrypt.co/story</link><pubDate>{date}</pubDate></item></channel></rss>'
        return httpx.Response(200, content=xml.encode(), request=httpx.Request('GET', url))
    monkeypatch.setattr(HTTP_CLIENT, "get", fake_get)
    rows = asyncio.run(NewsService()._fetch("Decrypt", "https://decrypt.co/feed"))
    assert rows[0]["published_at_source"] == "FALLBACK"
    assert not annotate_related_reports(rows, now=NOW)[0]["related_coverage"]["reports"]


def test_generic_recovery_words_do_not_link_different_named_incidents():
    assert not linked(
        article("Whitehats recover 52 bitcoin from major Coldcard hack"),
        article("Whitehats recover 52 bitcoin from major Otherwallet hack", "Decrypt"),
    )


def test_cached_articles_are_reassessed_for_age_without_mutation():
    items = [article(ETF[0]), article(ETF[1], "Decrypt")]
    assert annotate_related_reports(items, now=NOW)[0]["related_coverage"]["reports"]
    assert not annotate_related_reports(items, now=NOW + timedelta(days=1))[0]["related_coverage"]["reports"]
    assert "related_coverage" not in items[0]
