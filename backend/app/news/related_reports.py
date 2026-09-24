"""Conservative RSS headline links for human comparison, never fact verification.

Version 1 recognizes ETF flows and asset recovery reports. It does not read the
articles, identify primary sources, or infer independence between publishers.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .assets import ASSETS, match_assets, visible_text

VERSION = 1
WINDOW = timedelta(hours=24)
PUBLISHERS = {
    "CoinDesk": "coindesk.com", "Cointelegraph": "cointelegraph.com",
    "Decrypt": "decrypt.co",
}
_BLOCKED = re.compile(
    r"\b(?:not|no|never|denies?|denied|false|fake|debunks?|debunked|correction|"
    r"corrected|retract\w*|rumou?r\w*|could|would|may|might|expects?|predict\w*|"
    r"forecast\w*|if|will|poised|set to|seeks?|last week|last month|last year|"
    r"weekly|monthly|annual|cumulative)\b|\?", re.I,
)
_WEEKDAYS = set("monday tuesday wednesday thursday friday saturday sunday".split())
_SCALE = {"": 1, "k": 1000, "thousand": 1000, "m": 10**6, "million": 10**6,
          "b": 10**9, "bn": 10**9, "billion": 10**9}
_DOLLARS = re.compile(r"\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(billion|million|thousand|bn|b|m|k)?\b", re.I)
_STOP = set("the a an to from in on at as by of for with into after before and or "
            "crypto cryptocurrency token tokens coin coins hackers hacker hack hacks "
            "exploit exploited breach stolen theft recovery recover recovered recovers "
            "evacuation evacuate evacuates move moves moved transfer transfers transferred "
            "whitehat whitehats white hats trust fund funds wallet wallets new report reports "
            "major massive large small million billion exchange platform protocol users "
            "security crypto digital investigation attack incident rescue update breaking".split())


def canonical_url(source: str, raw: str) -> str | None:
    """Only link to the declared publisher; tracking aliases are one article."""
    try:
        url = urlsplit(raw)
        host = (url.hostname or "").lower().removeprefix("www.")
        if (source not in PUBLISHERS or host != PUBLISHERS[source]
                or url.scheme not in {"http", "https"} or url.username or url.password
                or url.port not in {None, 80, 443} or not url.path.strip("/")):
            return None
        query = sorted((k, v) for k, v in parse_qsl(url.query)
                       if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"})
        return urlunsplit(("https", host, url.path.rstrip("/"), urlencode(query), ""))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class Headline:
    article: dict[str, Any]
    url: str
    published: datetime
    asset: str
    family: str
    amount: Decimal
    direction: str
    anchors: frozenset[str]
    weekdays: frozenset[str]


def _headline(article: dict[str, Any], now: datetime) -> Headline | None:
    # Legacy dates without provenance and parser fallbacks cannot establish age.
    if article.get("published_at_source") != "RSS":
        return None
    try:
        published = datetime.fromisoformat(article["published_at"].replace("Z", "+00:00"))
        if published.tzinfo is None or not timedelta(0) <= now - published <= WINDOW:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    url = canonical_url(article.get("source", ""), article.get("url", ""))
    title = visible_text(article.get("title", ""))
    if not url or _BLOCKED.search(title):
        return None
    assets = match_assets(title)
    if len(assets) != 1:  # Avoid assigning one amount to multiple assets.
        return None
    asset = assets[0]
    text = title.lower()
    weekdays = frozenset(set(re.findall(r"[a-z]+", text)) & _WEEKDAYS)
    if len(weekdays) > 1:
        return None
    if re.search(r"\betfs?\b", text):
        if re.search(r"\b(?:options?|futures|fees?|revenue|leverage|derivatives)\b", text):
            return None
        inflow = bool(re.search(r"\binflows?\b|\betfs?\s+(?:attract\w*|take|takes|took)\b", text))
        outflow = bool(re.search(r"\b(?:outflows?|lose|loses|lost|shed|sheds)\b", text))
        amounts = {Decimal(n.replace(",", "")) * _SCALE[scale.lower()]
                   for n, scale in _DOLLARS.findall(text)}
        if inflow == outflow or len(amounts) != 1:
            return None
        return Headline(article, url, published, asset, "ETF_FLOW", amounts.pop(),
                        "INFLOW" if inflow else "OUTFLOW", frozenset(), weekdays)

    if not re.search(r"\b(?:hack\w*|exploit\w*|stolen|breach|theft)\b", text):
        return None
    if not re.search(r"\b(?:recover\w*|evacuat\w*|white\s*hats?)\b", text):
        return None
    aliases = (asset.lower(), *ASSETS[asset])
    alias_pattern = "|".join(re.escape(alias) for alias in aliases)
    amounts = {Decimal(n.replace(",", "")) for n in re.findall(
        rf"\b(\d+(?:,\d{{3}})*(?:\.\d+)?)\s*[- ]?\s*(?:{alias_pattern})\b", text,
    )}
    excluded = _STOP | _WEEKDAYS | {word for alias in aliases for word in alias.split()}
    # Require a name-like capitalized term, not merely generic recovery words.
    anchors = frozenset(word.lower() for word in re.findall(r"\b[A-Z][A-Za-z0-9]+\b", title)
                        if len(word) >= 4 and word.lower() not in excluded)
    if len(amounts) != 1 or not anchors:
        return None
    return Headline(article, url, published, asset, "ASSET_RECOVERY", amounts.pop(),
                    "RECOVERY", anchors, weekdays)


def annotate_related_reports(articles: list[dict[str, Any]], *, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    headlines = [_headline(article, now) for article in articles]
    result = []
    for article, candidate in zip(articles, headlines):
        reports: dict[str, dict[str, Any]] = {}
        if candidate:
            for other in headlines:
                if (other is None or other.article.get("source") == article.get("source")
                        or other.url == candidate.url
                        or (other.asset, other.family, other.amount, other.direction)
                        != (candidate.asset, candidate.family, candidate.amount, candidate.direction)
                        or abs(other.published - candidate.published) > WINDOW
                        or (candidate.weekdays and other.weekdays and candidate.weekdays != other.weekdays)):
                    continue
                shared = sorted(candidate.anchors & other.anchors)
                if candidate.family == "ASSET_RECOVERY" and not shared:
                    continue
                reports[other.url] = {
                    "source": other.article["source"], "title": other.article["title"],
                    "url": other.url, "published_at": other.article["published_at"],
                    "basis": {"family": candidate.family, "asset": candidate.asset,
                              "amount": str(candidate.amount),
                              "unit": "USD" if candidate.family == "ETF_FLOW" else candidate.asset,
                              "direction": candidate.direction, "shared_terms": shared},
                }
        links = sorted(reports.values(), key=lambda item: (item["published_at"], item["url"]), reverse=True)
        result.append({**article, "related_coverage": {
            "version": VERSION, "method": "RSS_HEADLINE_RULES",
            "checked_at": now.isoformat(),
            "other_publishers_count": len({item["source"] for item in links}),
            "reports": links,
        }})
    return result
