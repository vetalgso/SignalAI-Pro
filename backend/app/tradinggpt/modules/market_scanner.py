from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.tradinggpt.quality_guard import AnalysisQualityGuard
from app.tradinggpt.scoring import ScoringEngine


DEFAULT_SCAN_ASSETS = [
    "BTC",
    "ETH",
    "BNB",
    "SOL",
    "XRP",
    "ADA",
    "DOGE",
    "AVAX",
]


@dataclass(slots=True)
class ScannerResult:
    asset: str
    symbol: str
    score: float
    opportunity_score: float
    confidence: int
    risk: str
    recommendation: str
    trade_direction: str
    signal_action: str | None
    forecast_direction: str | None
    quality_penalty: int
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "symbol": self.symbol,
            "score": round(self.score, 2),
            "opportunity_score": round(self.opportunity_score, 2),
            "confidence": self.confidence,
            "risk": self.risk,
            "recommendation": self.recommendation,
            "trade_direction": self.trade_direction,
            "signal_action": self.signal_action,
            "forecast_direction": self.forecast_direction,
            "quality_penalty": self.quality_penalty,
            "warnings": self.warnings,
        }


class CryptoMarketScanner:
    def __init__(self, crypto_asset_module: Any) -> None:
        self.crypto_asset_module = crypto_asset_module

    async def scan(
        self,
        assets: list[str] | None = None,
        risk_level: str = "medium",
        limit: int = 5,
    ) -> dict[str, Any]:
        normalized_assets = self._normalize_assets(assets)

        tasks = [
            self._analyze_asset(asset=asset, risk_level=risk_level)
            for asset in normalized_assets
        ]

        raw_results = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        results: list[ScannerResult] = []
        errors: list[dict[str, str]] = []

        for asset, result in zip(normalized_assets, raw_results, strict=True):
            if isinstance(result, Exception):
                errors.append(
                    {
                        "asset": asset,
                        "error": result.__class__.__name__,
                    }
                )
                continue

            if result is not None:
                results.append(result)

        ranked = sorted(
            results,
            key=lambda item: (
                item.opportunity_score,
                item.confidence,
                -item.quality_penalty,
            ),
            reverse=True,
        )

        opportunities = [
            item
            for item in ranked
            if item.recommendation in {
                "LONG",
                "SHORT",
                "CAUTIOUS_BUY",
                "CAUTIOUS_SHORT",
            }
        ][:limit]

        watchlist = [
            item
            for item in ranked
            if item.recommendation == "WAIT"
        ][:limit]

        avoid = [
            item
            for item in reversed(ranked)
            if (
                item.risk == "high"
                and item.confidence < 35
            )
        ][:limit]

        return {
            "scanned_assets": len(normalized_assets),
            "successful_assets": len(results),
            "failed_assets": len(errors),
            "opportunities": [
                item.to_dict()
                for item in opportunities
            ],
            "watchlist": [
                item.to_dict()
                for item in watchlist
            ],
            "avoid": [
                item.to_dict()
                for item in avoid
            ],
            "ranking": [
                item.to_dict()
                for item in ranked[:limit]
            ],
            "errors": errors,
        }

    async def _analyze_asset(
        self,
        asset: str,
        risk_level: str,
    ) -> ScannerResult | None:
        symbol = f"{asset}USDT"

        signal, forecast, news = await asyncio.gather(
            self.crypto_asset_module._load_signal(symbol),
            self.crypto_asset_module._load_forecasts(symbol),
            self.crypto_asset_module._load_news(asset),
        )

        signal_score = self.crypto_asset_module._signal_score(signal)
        forecast_score = self.crypto_asset_module._forecast_score(forecast)
        news_score = self.crypto_asset_module._news_score(news)

        score, confidence = self.crypto_asset_module._combined_score(
            signal_score=signal_score,
            forecast_score=forecast_score,
            news_score=news_score,
            signal_available=signal is not None,
            forecast_available=forecast is not None,
            news_available=news is not None,
        )

        quality_penalty, warnings = (
            AnalysisQualityGuard.confidence_penalty(
                signal=signal,
                forecast=forecast,
                news=news,
            )
        )

        confidence = max(15, confidence - quality_penalty)

        trade_direction = ScoringEngine.trade_direction(score)
        opportunity_score = ScoringEngine.opportunity_score(
            score,
            confidence,
        )

        recommendation = ScoringEngine.recommendation(
            score,
            confidence,
            opportunity_score,
        )

        risk = self.crypto_asset_module._risk_level(
            signal,
            forecast,
            risk_level,
        )

        signal_action = None
        if signal:
            signal_action = (
                signal.get("decision", {}).get("action")
            )

        forecast_direction = self._primary_forecast_direction(
            forecast
        )

        return ScannerResult(
            asset=asset,
            symbol=symbol,
            score=score,
            opportunity_score=opportunity_score,
            confidence=confidence,
            risk=risk,
            recommendation=recommendation,
            trade_direction=trade_direction,
            signal_action=signal_action,
            forecast_direction=forecast_direction,
            quality_penalty=quality_penalty,
            warnings=warnings,
        )

    @staticmethod
    def _normalize_assets(
        assets: list[str] | None,
    ) -> list[str]:
        source = assets or DEFAULT_SCAN_ASSETS

        normalized: list[str] = []

        for asset in source:
            clean = asset.upper().replace("USDT", "").strip()

            if clean and clean not in normalized:
                normalized.append(clean)

        return normalized[:20]

    @staticmethod
    def _primary_forecast_direction(
        forecast: dict[str, Any] | None,
    ) -> str | None:
        if not forecast:
            return None

        items = forecast.get("forecasts", [])

        if not items:
            return None

        preferred = next(
            (
                item
                for item in items
                if item.get("horizon_minutes") == 1440
            ),
            None,
        )

        selected = preferred or max(
            items,
            key=lambda item: item.get("confidence", 0),
        )

        return selected.get("direction")
