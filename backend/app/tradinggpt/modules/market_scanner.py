from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.tradinggpt.quality_guard import AnalysisQualityGuard
from app.tradinggpt.scoring import ScoringEngine
from app.tradinggpt.signals.market_universe import (
    BinanceLiquidMarketUniverse,
    FALLBACK_ASSETS,
)


DEFAULT_SCAN_ASSETS = FALLBACK_ASSETS
MAX_CONCURRENT_ASSET_ANALYSES = 5


@dataclass(slots=True)
class ScannerResult:
    asset: str
    symbol: str
    score: float
    opportunity_score: float
    consensus_score: float
    timeframe_consensus_score: float
    ranking_score: float
    confidence: int
    risk: str
    recommendation: str
    trade_direction: str
    signal_action: str | None
    forecast_direction: str | None
    timeframe_directions: dict[str, str]
    trend_direction: str
    trade_style: str
    reasons: list[str]
    quality_penalty: int
    warnings: list[str]
    market_price: float | None = None
    signal_strategy: str | None = None
    signal_levels: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "symbol": self.symbol,
            "score": round(self.score, 2),
            "opportunity_score": round(self.opportunity_score, 2),
            "consensus_score": round(self.consensus_score, 2),
            "timeframe_consensus_score": round(
                self.timeframe_consensus_score,
                2,
            ),
            "ranking_score": round(self.ranking_score, 2),
            "confidence": self.confidence,
            "risk": self.risk,
            "recommendation": self.recommendation,
            "trade_direction": self.trade_direction,
            "signal_action": self.signal_action,
            "forecast_direction": self.forecast_direction,
            "timeframe_directions": self.timeframe_directions,
            "trend_direction": self.trend_direction,
            "trade_style": self.trade_style,
            "reasons": self.reasons,
            "quality_penalty": self.quality_penalty,
            "warnings": self.warnings,
            "market_price": self.market_price,
            "signal_strategy": self.signal_strategy,
            "signal_levels": self.signal_levels,
        }


class CryptoMarketScanner:
    def __init__(
        self,
        crypto_asset_module: Any,
        universe_provider: Any | None = None,
    ) -> None:
        self.crypto_asset_module = crypto_asset_module
        self.universe_provider = (
            universe_provider or BinanceLiquidMarketUniverse()
        )

    async def scan(
        self,
        assets: list[str] | None = None,
        risk_level: str = "medium",
        limit: int = 5,
    ) -> dict[str, Any]:
        universe_source = "EXPLICIT"
        universe_warnings: list[str] = []

        if assets:
            normalized_assets = self._normalize_assets(assets)
        else:
            selection = await self.universe_provider.select(limit=limit)
            normalized_assets = self._normalize_assets(
                selection.assets,
                limit=limit,
            )
            universe_source = selection.source
            universe_warnings = list(selection.warnings)

        semaphore = asyncio.Semaphore(
            MAX_CONCURRENT_ASSET_ANALYSES
        )

        async def analyze_bounded(
            asset: str,
        ) -> ScannerResult | None:
            async with semaphore:
                return await self._analyze_asset(
                    asset=asset,
                    risk_level=risk_level,
                )

        tasks = [
            analyze_bounded(asset)
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
                    self._scanner_error(
                        asset,
                        result,
                    )
                )
                continue

            if result is not None:
                results.append(result)

        ranked = sorted(
            results,
            key=lambda item: (
                item.ranking_score,
                item.timeframe_consensus_score,
                item.opportunity_score,
                item.consensus_score,
                item.confidence,
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

        candidates = [item.to_dict() for item in ranked]

        scanner_rejections: dict[str, int] = {}

        for item in ranked:
            reason = self._scanner_rejection_reason(item)

            if reason is not None:
                scanner_rejections[reason] = (
                    scanner_rejections.get(reason, 0) + 1
                )

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
            "universe_source": universe_source,
            "universe_assets": normalized_assets,
            "universe_warnings": universe_warnings,
            "scanned_assets": len(normalized_assets),
            "successful_assets": len(results),
            "failed_assets": len(errors),
            "opportunities": [
                item.to_dict()
                for item in opportunities
            ],
            "candidates": candidates,
            "candidate_count": len(candidates),
            "scanner_rejections": scanner_rejections,
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

        consensus_score = ScoringEngine.consensus_score(
            combined_direction=trade_direction,
            signal_score=signal_score,
            forecast_score=forecast_score,
            news_score=news_score,
            signal_available=signal is not None,
            forecast_available=forecast is not None,
            news_available=news is not None,
        )

        opportunity_score = ScoringEngine.opportunity_score(
            score,
            confidence,
            consensus_score,
        )

        timeframe_analysis = ScoringEngine.timeframe_analysis(
            forecast,
            trade_direction,
        )

        timeframe_consensus_score = float(
            timeframe_analysis["timeframe_consensus_score"]
        )

        ranking_score = ScoringEngine.ranking_score(
            opportunity_score,
            consensus_score,
            confidence,
            timeframe_consensus_score,
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
        market_price = None
        signal_strategy = None
        signal_levels = None

        if signal:
            decision = signal.get(
                "decision",
                {},
            )

            signal_action = decision.get(
                "action"
            )
            signal_strategy = decision.get(
                "strategy"
            )
            market_price = signal.get(
                "price"
            )

            raw_levels = decision.get(
                "levels"
            )

            if isinstance(raw_levels, dict):
                signal_levels = raw_levels

        forecast_direction = self._primary_forecast_direction(
            forecast
        )

        reasons = ScoringEngine.explanation_reasons(
            signal=signal,
            news=news,
            trade_direction=trade_direction,
            consensus_score=consensus_score,
            timeframe_analysis=timeframe_analysis,
            risk=risk,
        )

        return ScannerResult(
            asset=asset,
            symbol=symbol,
            score=score,
            opportunity_score=opportunity_score,
            consensus_score=consensus_score,
            timeframe_consensus_score=timeframe_consensus_score,
            ranking_score=ranking_score,
            confidence=confidence,
            risk=risk,
            recommendation=recommendation,
            trade_direction=trade_direction,
            signal_action=signal_action,
            forecast_direction=forecast_direction,
            timeframe_directions=timeframe_analysis["directions"],
            trend_direction=timeframe_analysis["trend_direction"],
            trade_style=timeframe_analysis["trade_style"],
            reasons=reasons,
            quality_penalty=quality_penalty,
            warnings=warnings,
            market_price=market_price,
            signal_strategy=signal_strategy,
            signal_levels=signal_levels,
        )

    @staticmethod
    def _scanner_error(
        asset: str,
        error: Exception,
    ) -> dict[str, str]:
        error_name = error.__class__.__name__

        if error_name in {
            "TimeoutError",
            "ReadTimeout",
            "ConnectTimeout",
            "PoolTimeout",
        }:
            error_code = "UPSTREAM_TIMEOUT"
        elif error_name in {
            "ConnectionError",
            "ConnectError",
            "NetworkError",
            "RemoteProtocolError",
        }:
            error_code = "UPSTREAM_CONNECTION_ERROR"
        elif error_name in {
            "TypeError",
            "ValueError",
            "KeyError",
            "IndexError",
            "AttributeError",
        }:
            error_code = "INVALID_ANALYSIS_PAYLOAD"
        else:
            error_code = "UNEXPECTED_ANALYSIS_ERROR"

        location = "UNKNOWN"
        traceback = error.__traceback__

        while (
            traceback is not None
            and traceback.tb_next is not None
        ):
            traceback = traceback.tb_next

        if traceback is not None:
            code = traceback.tb_frame.f_code
            filename = (
                code.co_filename
                .rsplit("/", 1)[-1]
                .rsplit("\\", 1)[-1]
            )
            location = (
                f"{filename}:"
                f"{code.co_name}:"
                f"{traceback.tb_lineno}"
            )

        return {
            "asset": asset,
            "error": error_name,
            "error_code": error_code,
            "stage": "ASSET_ANALYSIS",
            "location": location,
        }

    @staticmethod
    def _normalize_assets(
        assets: list[str] | None,
        *,
        limit: int = 100,
    ) -> list[str]:
        source = assets or DEFAULT_SCAN_ASSETS

        normalized: list[str] = []

        for asset in source:
            clean = asset.upper().replace("USDT", "").strip()

            if clean and clean not in normalized:
                normalized.append(clean)

        return normalized[:max(1, min(int(limit), 100))]

    @staticmethod
    def _scanner_rejection_reason(item: ScannerResult) -> str | None:
        if item.signal_action not in {"LONG", "SHORT"}:
            return "NO_ACTIONABLE_TECHNICAL_SIGNAL"

        if item.trade_direction != item.signal_action:
            return "DIRECTION_CONFLICT"

        if item.recommendation not in {
            "LONG",
            "SHORT",
            "CAUTIOUS_BUY",
            "CAUTIOUS_SHORT",
        }:
            return "RECOMMENDATION_NOT_ACTIONABLE"

        if item.signal_levels is None:
            return "LEVELS_UNAVAILABLE"

        return None

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
