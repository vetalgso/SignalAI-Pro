from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.tradinggpt.engine.schemas import TradingGPTAnalyzeRequest


@pytest.fixture(scope="session")
def analysis_payload() -> dict[str, Any]:
    return {
        "scoring": {
            "score": 82.0,
            "opportunity_score": 85.0,
            "consensus_score": 70.0,
            "confidence": 90,
            "trade_direction": "LONG",
            "signal_score": 80.0,
            "forecast_score": 84.0,
            "news_score": 76.0,
        },
        "market_regime": {
            "market_regime": "RISK_ON",
            "confidence": 0.88,
            "trend_regime": "BULL",
            "risk_environment": "RISK_ON",
            "risk_asset_score": 78.0,
            "defensive_asset_score": 22.0,
            "risk_appetite_score": 75.0,
            "market_breadth_score": 0.72,
            "volatility_score": 35.0,
            "signals": [],
            "reasons": [
                "Risk assets are broadly supported."
            ],
            "warnings": [],
        },
        "portfolio": {
            "capital": 10000.0,
            "currency": "USD",
            "risk_level": "medium",
            "max_position_percent": 25.0,
            "max_risk_per_trade_percent": 1.0,
            "portfolio_risk_score": 30.0,
            "cash_reserve_percent": 20.0,
            "invested_percent": 80.0,
            "positions": [],
            "trades": [],
            "min_trade_amount": 25.0,
            "trading_fee_percent": 0.1,
            "rebalance_tolerance_percent": 0.5,
            "trade_rounding_amount": 1.0,
            "estimated_total_fees": 0.0,
            "warnings": [],
        },
    }


@pytest.fixture(scope="session")
def analyze_request(
    analysis_payload: dict[str, Any],
) -> TradingGPTAnalyzeRequest:
    return TradingGPTAnalyzeRequest.model_validate(
        analysis_payload
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    isolated_session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Iterator[Session]:
        session = isolated_session_factory()

        try:
            yield session
        finally:
            session.close()

    safety_fields = (
        "scheduler_background_loop_enabled",
        "order_reconciliation_background_enabled",
        "signal_tracking_enabled",
        "signal_scanner_background_enabled",
        "telegram_signal_enabled",
    )

    previous_settings = {
        name: getattr(settings, name)
        for name in safety_fields
    }

    previous_db_override = (
        app.dependency_overrides.get(get_db)
    )

    for name in safety_fields:
        setattr(settings, name, False)

    app.dependency_overrides[get_db] = (
        override_get_db
    )

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        if previous_db_override is None:
            app.dependency_overrides.pop(
                get_db,
                None,
            )
        else:
            app.dependency_overrides[get_db] = (
                previous_db_override
            )

        for name, value in (
            previous_settings.items()
        ):
            setattr(settings, name, value)

        Base.metadata.drop_all(bind=engine)
        engine.dispose()
