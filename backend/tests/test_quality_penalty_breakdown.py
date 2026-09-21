import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.signal_discovery import SignalScanCandidate
from app.tradinggpt.modules.crypto_asset import CryptoAssetAnalysisModule
from app.tradinggpt.modules.market_scanner import CryptoMarketScanner
from app.tradinggpt.quality_details import read_quality_breakdown
from app.tradinggpt.quality_guard import AnalysisQualityGuard as Guard
from app.tradinggpt.scoring import ScoringEngine
from app.tradinggpt.signals.discovery_repository import SignalDiscoveryRepository


def inputs(uncertain=1, ratio=0.6, unverified=1):
    return {
        "signal": {"price": 100, "decision": {"action": "LONG", "confidence": 80},
                   "indicators": {"volume": {"ratio": ratio}}},
        "forecast": {"forecasts": [
            {"horizon_minutes": h, "direction": "UNCERTAIN" if i < uncertain else "UP",
             "probabilities": {"up": 0.45, "down": 0.30, "sideways": 0.25},
             "confidence": 45, "expected_change_percent": 1}
            for i, h in enumerate([60, 240, 1440, 2880])
        ]},
        "news": {"articles": [{"status": "unverified" if i < unverified else "verified"}
                              for i in range(2)]},
    }


@pytest.mark.parametrize("uncertain,ratio,unverified,parts,total", [
    (0, 0.8, 0, (0, 0, 0), 0),
    (1, 0.5, 1, (5, 5, 5), 15),
    (2, 0.25, 1, (10, 10, 5), 25),
    (3, 0.24, 2, (15, 15, 10), 30),
])
def test_breakdown_preserves_penalty_thresholds_and_cap(uncertain, ratio, unverified, parts, total):
    payload = inputs(uncertain, ratio, unverified)
    before = deepcopy(payload)
    details = Guard.quality_breakdown(**payload)
    assert (details.forecast.points, details.volume.points, details.news.points) == parts
    assert details.uncapped_total == sum(parts)
    assert details.total == Guard.confidence_penalty(**payload)[0] == total
    assert details.forecast.uncertain_count == uncertain
    assert len(details.forecast.horizons) == 4
    assert details.forecast.horizons[-1].horizon_minutes == 2880
    assert details.news.unverified_count == unverified
    assert details.calculated_at.tzinfo is not None
    assert payload == before


def test_quarter_uncertain_warning_does_not_claim_majority():
    penalty, warnings = Guard.confidence_penalty(**inputs())
    assert penalty == 15
    assert any("1 из 4" in warning for warning in warnings)
    assert not any("Большинство" in warning for warning in warnings)


@pytest.mark.parametrize("forecast,news", [
    (None, None), ({"forecasts": None}, {"articles": None}),
    ({"forecasts": []}, {"articles": []}),
])
def test_missing_data_has_accurate_explanation_and_same_penalty(forecast, news):
    details = Guard.quality_breakdown(signal=None, forecast=forecast, news=news)
    assert details.total == 30
    assert (details.forecast.points, details.volume.points, details.news.points) == (15, 10, 5)
    assert {details.forecast.state, details.volume.state, details.news.state} == {"MISSING"}
    warnings = Guard.quality_warnings(details)
    assert len(warnings) == 3
    assert all("отсутств" in warning for warning in warnings)
    assert not any("ниже среднего" in warning or "не подтверждено" in warning for warning in warnings)


@pytest.mark.parametrize("ratio,state,penalty", [
    (None, "MISSING", 10), ("bad", "INVALID", 10),
    (float("nan"), "INVALID", 10), (float("inf"), "INVALID", 0),
    (float("-inf"), "INVALID", 15), (0, "AVAILABLE", 15),
])
def test_volume_diagnostics_are_json_safe_without_rescoring(ratio, state, penalty):
    details = Guard.quality_breakdown(**inputs(ratio=ratio))
    assert details.volume.state == state
    assert details.volume.points == penalty
    if state != "AVAILABLE":
        assert details.volume.ratio is None
    serialized = details.model_dump_json()
    assert "NaN" not in serialized and "Infinity" not in serialized


def test_raw_uncertainty_is_preserved_beside_derived_long_labels():
    payload = inputs(uncertain=4)
    details = Guard.quality_breakdown(**payload)
    derived = ScoringEngine.timeframe_analysis(payload["forecast"], "LONG")
    assert derived["directions"] == {"1H": "LONG", "4H": "LONG", "1D": "LONG"}
    assert all(h.direction == "UNCERTAIN" for h in details.forecast.horizons)
    assert details.forecast.points == 15


def test_projection_filters_private_data_and_refuses_inconsistent_history():
    details = Guard.quality_breakdown(**inputs()).model_dump(mode="json")
    details["secret"] = "private"
    details["news"]["articles"] = [{"token": "private"}]
    snapshot = {"quality_penalty": 15, "quality_breakdown": details}
    result = read_quality_breakdown(snapshot)
    assert result is not None and "private" not in result.model_dump_json()
    assert read_quality_breakdown({"quality_penalty": 15}) is None
    assert read_quality_breakdown({"quality_penalty": 30, "quality_breakdown": details}) is None
    for name, value in (("total", 1), ("version", 2), ("calculated_at", "bad")):
        broken = deepcopy(details)
        broken[name] = value
        assert read_quality_breakdown({"quality_penalty": 15, "quality_breakdown": broken}) is None


def test_scanner_journal_roundtrip_keeps_quality_and_old_rows_unknown():
    payload = inputs(uncertain=2, ratio=0.25)

    class FixtureModule(CryptoAssetAnalysisModule):
        def __init__(self):
            pass
        async def _load_signal(self, symbol):
            return payload["signal"]
        async def _load_forecasts(self, symbol):
            return payload["forecast"]
        async def _load_news(self, asset):
            return payload["news"]

    scan = asyncio.run(CryptoMarketScanner(FixtureModule()).scan(assets=["SOL"], limit=1))
    assert scan["failed_assets"] == 0
    raw = scan["candidates"][0]
    assert raw["quality_penalty"] == 25
    assert raw["quality_breakdown"]["uncapped_total"] == 25
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        now = datetime.now(timezone.utc)
        run = SignalDiscoveryRepository(db).record_completed_scan(
            scan_result=scan, persistence_result={"evaluations": [
                {"symbol": "SOLUSDT", "outcome": "REJECTED", "reason": "RECOMMENDATION_CONFLICT"},
            ]}, risk_level="medium", minimum_confidence=Decimal(60), requested_limit=1,
            started_at=now, completed_at=now,
        )
        candidate = db.scalar(select(SignalScanCandidate).where(SignalScanCandidate.run_id == run.id))
        assert read_quality_breakdown(candidate.snapshot).total == 25
        assert candidate.snapshot["quality_breakdown"] == raw["quality_breakdown"]
        # The API reads the saved breakdown; it does not invoke market providers.
        from app.tradinggpt.signals.ai_admission_read import list_ai_admission
        page = list_ai_admission(run_id=run.id, limit=25, offset=0, db=db)
        assert page.items[0].quality.volume.ratio == 0.25
        assert page.items[0].decision is None
        candidate.snapshot = {"quality_penalty": 25, "warnings": ["legacy warning"]}
        db.commit()
        page = list_ai_admission(run_id=run.id, limit=25, offset=0, db=db)
        assert page.items[0].quality is None
    engine.dispose()
