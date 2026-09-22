import asyncio
from copy import deepcopy

import pytest

from app.news.service import ASSETS, FEEDS, NewsService
from app.tradinggpt.modules.crypto_asset import CryptoAssetAnalysisModule
from app.tradinggpt.quality_guard import AnalysisQualityGuard
from app.tradinggpt.risk_assessment import assess_risk, read_risk_assessment


def signal(ratio=1, warnings=0):
    return {"decision": {"warnings": ["warning"] * warnings},
            "indicators": {"volume": {"ratio": ratio}}}


def forecast(*levels):
    return {"forecasts": [{"horizon_minutes": h, "risk_level": level}
                          for h, level in zip([60, 240, 1440, 2880], levels)]}


@pytest.mark.parametrize("s,f,profile,level,reason", [
    (signal(), forecast("normal", "high"), "medium", "high", "FORECAST_HIGH"),
    (signal(), forecast("elevated", "elevated"), "medium", "high", "MULTIPLE_ELEVATED"),
    (signal(), forecast("elevated"), "high", "high", "PROFILE_WITH_ELEVATED"),
    (signal(None), forecast(), "medium", "high", "INVALID_VOLUME"),
    (signal("bad"), forecast(), "medium", "high", "INVALID_VOLUME"),
    (signal(float("nan")), forecast(), "medium", "high", "INVALID_VOLUME"),
    (signal(1, 2), forecast(), "medium", "high", "SIGNAL_WARNINGS"),
    (signal(0.249), forecast(), "medium", "high", "LOW_VOLUME"),
    (signal(0.25, 1), forecast(), "medium", "medium", "PROFILE"),
    (signal(), forecast("elevated"), "medium", "medium", "PROFILE"),
    (None, None, "low", "low", "PROFILE"),
    (signal(), forecast(), "high", "high", "PROFILE"),
    # Existing infinity behavior is preserved while the diagnostic stays JSON safe.
    (signal(float("inf")), forecast(), "medium", "medium", "PROFILE"),
    (signal(float("-inf")), forecast(), "medium", "high", "LOW_VOLUME"),
    # Earlier rules have priority even when later rules also match.
    (signal(None, 3), forecast("high", "elevated", "elevated"), "high", "high", "FORECAST_HIGH"),
    (signal(0.1, 2), forecast(), "medium", "high", "SIGNAL_WARNINGS"),
])
def test_original_risk_boundaries_and_first_reason(s, f, profile, level, reason):
    detail = assess_risk(s, f, profile)
    assert detail.level == CryptoAssetAnalysisModule._risk_level(s, f, profile) == level
    assert detail.reason == reason
    assert detail.calculated_at.tzinfo is not None
    assert "NaN" not in detail.model_dump_json() and "Infinity" not in detail.model_dump_json()


def test_risk_projection_preserves_history_and_excludes_extra_data():
    detail = assess_risk(signal(), forecast("normal", "high"), "medium").model_dump(mode="json")
    detail["private"] = "provider token"
    snapshot = {"risk_assessment": detail}
    assert "provider token" not in read_risk_assessment(snapshot, "HIGH").model_dump_json()
    assert read_risk_assessment(snapshot, "LOW") is None
    assert read_risk_assessment({}, "HIGH") is None
    for key, value in (("version", 2), ("reason", "made up"), ("calculated_at", "bad")):
        broken = deepcopy(detail)
        broken[key] = value
        assert read_risk_assessment({"risk_assessment": broken}, "HIGH") is None


@pytest.mark.parametrize("asset,fail_count,matching,coverage,source_state", [
    ("ZEC", 0, False, "UNSUPPORTED", "COMPLETE"),
    ("NEAR", 1, False, "UNSUPPORTED", "PARTIAL"),
    ("CRCLB", 3, False, "UNSUPPORTED", "FAILED"),
    ("BTC", 0, False, "SUPPORTED", "COMPLETE"),
    ("BTC", 1, False, "SUPPORTED", "PARTIAL"),
    ("BTC", 3, False, "SUPPORTED", "FAILED"),
    ("btc", 0, True, "SUPPORTED", "COMPLETE"),
    ("BTC", 1, True, "SUPPORTED", "PARTIAL"),
    (None, 0, True, "ALL", "COMPLETE"),
])
def test_news_coverage_is_independent_of_source_health(monkeypatch, asset, fail_count, matching, coverage, source_state):
    monkeypatch.setattr(NewsService, "_feed_cache", None)
    monkeypatch.setattr(NewsService, "_feed_load_task", None)
    failed = {name for name, _ in FEEDS[:fail_count]}
    service = NewsService()

    async def fetch(name, url):
        if name in failed:
            raise RuntimeError("private URL or token must never be returned")
        return [{"id": name, "published_at": "2026-09-22T12:00:00Z", "source": name,
                 "assets": ["BTC"] if matching else ["ETH"], "status": "unverified"}]

    monkeypatch.setattr(service, "_fetch", fetch)
    result = asyncio.run(service.latest(asset=asset, limit=1))
    detail = result["diagnostics"]
    assert detail["coverage"] == coverage
    assert detail["sources_state"] == source_state
    assert detail["failed_sources"] == fail_count
    assert detail["collected_articles"] == 3 - fail_count
    assert result["partial"] == bool(fail_count)
    assert "private" not in str(result)
    assert result["count"] == (1 if matching and fail_count < 3 else 0)
    if matching:
        assert detail["matched_articles"] == 3 - fail_count
    quality = AnalysisQualityGuard.quality_breakdown(signal=None, forecast=None, news=result)
    assert quality.news.diagnostics.coverage == coverage
    assert quality.news.points == (10 if result["count"] else 5)
    assert quality.news.diagnostics.sources_state == source_state


def test_empty_successful_feeds_are_distinct_from_errors(monkeypatch):
    service = NewsService()
    async def empty():
        return [], []
    monkeypatch.setattr(service, "_all_articles", empty)
    result = asyncio.run(service.latest(asset="BTC"))
    assert result["diagnostics"]["sources_state"] == "COMPLETE"
    assert result["diagnostics"]["collected_articles"] == 0
    assert result["diagnostics"]["coverage"] == "SUPPORTED"
    legacy = AnalysisQualityGuard.quality_breakdown(signal=None, forecast=None, news={"articles": []})
    assert legacy.news.diagnostics is None
