from __future__ import annotations

import asyncio
from typing import Any

from app.forecasting import ForecastService
from app.indicators.service import calculate_indicator_snapshot
from app.news import NewsService
from app.services.binance_market import BinanceMarketService
from app.signal_engine.service import build_signal_analysis
from app.tradinggpt.quality_guard import AnalysisQualityGuard
from app.tradinggpt.schemas import (
    AnalysisFactor,
    AssistantChatRequest,
    AssistantChatResponse,
)


DISCLAIMER = (
    "Информация носит аналитический характер и не является индивидуальной "
    "инвестиционной рекомендацией или гарантией результата."
)

SUPPORTED_CRYPTO_ASSETS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "BNB": "BNBUSDT",
    "SOL": "SOLUSDT",
    "XRP": "XRPUSDT",
    "ADA": "ADAUSDT",
    "DOGE": "DOGEUSDT",
    "TRX": "TRXUSDT",
    "AVAX": "AVAXUSDT",
    "LINK": "LINKUSDT",
}

FORECAST_HORIZONS = [60, 240, 1440, 2880]


class CryptoAssetAnalysisModule:
    async def analyze(
        self,
        asset: str,
        request: AssistantChatRequest,
    ) -> AssistantChatResponse:
        normalized_asset = asset.upper()

        if normalized_asset not in SUPPORTED_CRYPTO_ASSETS:
            return self._unsupported_response(normalized_asset, request)

        symbol = SUPPORTED_CRYPTO_ASSETS[normalized_asset]

        signal_result, forecast_result, news_result = await asyncio.gather(
            self._load_signal(symbol),
            self._load_forecasts(symbol),
            self._load_news(normalized_asset),
        )

        available_sources = sum(
            result is not None
            for result in (signal_result, forecast_result, news_result)
        )

        if available_sources == 0:
            return self._unavailable_response(normalized_asset, request)

        return self._build_response(
            asset=normalized_asset,
            symbol=symbol,
            request=request,
            signal=signal_result,
            forecast=forecast_result,
            news=news_result,
            available_sources=available_sources,
        )

    async def _load_signal(self, symbol: str) -> dict[str, Any] | None:
        try:
            candles = await BinanceMarketService().klines(symbol, "1h", 250)
            snapshot = calculate_indicator_snapshot(candles)
            decision = build_signal_analysis(snapshot)

            return {
                "symbol": symbol,
                "interval": "1h",
                "price": float(snapshot["price"]),
                "indicators": snapshot,
                "decision": decision,
            }
        except Exception:
            return None

    async def _load_forecasts(self, symbol: str) -> dict[str, Any] | None:
        try:
            return await ForecastService().forecast(
                symbol,
                FORECAST_HORIZONS,
            )
        except Exception:
            return None

    async def _load_news(self, asset: str) -> dict[str, Any] | None:
        try:
            return await NewsService().latest(limit=10, asset=asset)
        except Exception:
            return None

    def _build_response(
        self,
        *,
        asset: str,
        symbol: str,
        request: AssistantChatRequest,
        signal: dict[str, Any] | None,
        forecast: dict[str, Any] | None,
        news: dict[str, Any] | None,
        available_sources: int,
    ) -> AssistantChatResponse:
        signal_score = self._signal_score(signal)
        forecast_score = self._forecast_score(forecast)
        news_score = self._news_score(news)

        weighted_score, confidence = self._combined_score(
            signal_score=signal_score,
            forecast_score=forecast_score,
            news_score=news_score,
            signal_available=signal is not None,
            forecast_available=forecast is not None,
            news_available=news is not None,
        )

        quality_penalty, quality_warnings = (
            AnalysisQualityGuard.confidence_penalty(
                signal=signal,
                forecast=forecast,
                news=news,
            )
        )

        confidence = max(15, confidence - quality_penalty)

        market_view = self._market_view(weighted_score)
        risk = self._risk_level(signal, forecast, request.context.risk_level)
        recommendation = self._recommendation(weighted_score, confidence)

        factors: list[AnalysisFactor] = []

        if signal:
            decision = signal["decision"]
            factors.append(
                AnalysisFactor(
                    type="technical",
                    score=round(signal_score),
                    summary=self._signal_summary(decision),
                )
            )
        else:
            factors.append(
                AnalysisFactor(
                    type="technical",
                    score=0,
                    summary="Технический анализ временно недоступен.",
                )
            )

        if forecast:
            factors.append(
                AnalysisFactor(
                    type="forecast",
                    score=round(forecast_score),
                    summary=self._forecast_summary(forecast),
                )
            )
        else:
            factors.append(
                AnalysisFactor(
                    type="forecast",
                    score=0,
                    summary="Прогнозы временно недоступны.",
                )
            )

        if news:
            factors.append(
                AnalysisFactor(
                    type="news",
                    score=round(news_score),
                    summary=self._news_summary(news),
                )
            )
        else:
            factors.append(
                AnalysisFactor(
                    type="news",
                    score=0,
                    summary="Новости временно недоступны.",
                )
            )

        factors.append(
            AnalysisFactor(
                type="data_quality",
                score=max(0, 100 - quality_penalty * 3),
                summary=(
                    "Качество подтверждения достаточное."
                    if not quality_warnings
                    else " ".join(quality_warnings)
                ),
            )
        )

        answer = self._build_answer(
            asset=asset,
            recommendation=recommendation,
            confidence=confidence,
            market_view=market_view,
            risk=risk,
            signal=signal,
            forecast=forecast,
            news=news,
            available_sources=available_sources,
        )

        return AssistantChatResponse(
            intent="asset_analysis",
            answer=answer,
            confidence=confidence,
            risk=risk,
            market_view=market_view,
            factors=factors,
            follow_up_questions=[
                f"На какой срок вы планируете покупать {asset}?",
                "Какую долю капитала вы готовы вложить?",
                "Нужно ли рассчитать размер позиции и уровни риска?",
            ],
            details={
                "asset": asset,
                "symbol": symbol,
                "recommendation": recommendation,
                "combined_score": round(weighted_score, 2),
                "sources_available": available_sources,
                "quality_penalty": quality_penalty,
                "quality_warnings": quality_warnings,
                "signal": signal,
                "forecast": forecast,
                "news": news,
            },
            disclaimer=DISCLAIMER,
        )

    @staticmethod
    def _signal_score(signal: dict[str, Any] | None) -> float:
        if not signal:
            return 50.0

        decision = signal["decision"]
        action = decision["action"]
        confidence = float(decision["confidence"])

        if action == "LONG":
            return 50 + confidence / 2

        if action == "SHORT":
            return 50 - confidence / 2

        scores = decision.get("score", {})
        long_score = float(scores.get("long_score", 0))
        short_score = float(scores.get("short_score", 0))

        return max(0.0, min(100.0, 50 + (long_score - short_score) / 2))

    @staticmethod
    def _forecast_score(forecast: dict[str, Any] | None) -> float:
        if not forecast or not forecast.get("forecasts"):
            return 50.0

        weighted_total = 0.0
        total_weight = 0.0

        for item in forecast["forecasts"]:
            probabilities = item["probabilities"]
            directional_score = (
                50
                + float(probabilities["up"]) * 50
                - float(probabilities["down"]) * 50
            )

            horizon = int(item["horizon_minutes"])
            weight = {
                60: 1.0,
                240: 1.1,
                1440: 1.25,
                2880: 1.0,
            }.get(horizon, 1.0)

            weighted_total += directional_score * weight
            total_weight += weight

        return max(0.0, min(100.0, weighted_total / total_weight))

    @staticmethod
    def _news_score(news: dict[str, Any] | None) -> float:
        if not news or not news.get("articles"):
            return 50.0

        weighted_sentiment = 0.0
        total_weight = 0.0

        for article in news["articles"]:
            sentiment_value = {
                "positive": 1.0,
                "neutral": 0.0,
                "negative": -1.0,
            }.get(article.get("sentiment"), 0.0)

            weight = max(1.0, float(article.get("impact_score", 50)))
            weighted_sentiment += sentiment_value * weight
            total_weight += weight

        normalized = weighted_sentiment / total_weight if total_weight else 0.0
        return max(0.0, min(100.0, 50 + normalized * 50))

    @staticmethod
    def _combined_score(
        *,
        signal_score: float,
        forecast_score: float,
        news_score: float,
        signal_available: bool,
        forecast_available: bool,
        news_available: bool,
    ) -> tuple[float, int]:
        sources = [
            (signal_score, 0.45, signal_available),
            (forecast_score, 0.40, forecast_available),
            (news_score, 0.15, news_available),
        ]

        weighted_total = 0.0
        total_weight = 0.0

        for score, weight, available in sources:
            if available:
                weighted_total += score * weight
                total_weight += weight

        if total_weight == 0:
            return 50.0, 0

        combined = weighted_total / total_weight
        distance_from_neutral = abs(combined - 50) * 2
        coverage = total_weight
        confidence = round(min(95, distance_from_neutral * 0.65 + coverage * 35))

        return combined, max(20, confidence)

    @staticmethod
    def _market_view(score: float) -> str:
        if score >= 62:
            return "bullish"

        if score <= 38:
            return "bearish"

        if 46 <= score <= 54:
            return "neutral"

        return "mixed"

    @staticmethod
    def _recommendation(score: float, confidence: int) -> str:
        if confidence < 35:
            return "WAIT"

        if score >= 68:
            return "BUY"

        if score >= 58:
            return "CAUTIOUS_BUY"

        if score <= 32:
            return "AVOID_OR_REDUCE"

        if score <= 42:
            return "CAUTIOUS_SELL"

        return "WAIT"

    @staticmethod
    def _risk_level(
        signal: dict[str, Any] | None,
        forecast: dict[str, Any] | None,
        profile_risk: str,
    ) -> str:
        forecast_risks: list[str] = []

        if forecast:
            forecast_risks = [
                item.get("risk_level", "normal")
                for item in forecast.get("forecasts", [])
            ]

        if "high" in forecast_risks:
            return "high"

        elevated_count = forecast_risks.count("elevated")

        if elevated_count >= 2:
            return "high"

        if elevated_count == 1 and profile_risk == "high":
            return "high"

        if signal:
            warnings = signal["decision"].get("warnings", [])

            volume_ratio = float(
                signal.get("indicators", {})
                .get("volume", {})
                .get("ratio", 1)
            )

            if len(warnings) >= 2 or volume_ratio < 0.25:
                return "high"

        return profile_risk

    @staticmethod
    def _signal_summary(decision: dict[str, Any]) -> str:
        action = decision["action"]
        confidence = decision["confidence"]
        reasons = decision.get("reasons", [])

        reason = reasons[0] if reasons else "Нет выраженного подтверждения."
        return f"Сигнал {action}, уверенность {confidence:.0f}%. {reason}"

    @staticmethod
    def _forecast_summary(forecast: dict[str, Any]) -> str:
        forecasts = forecast.get("forecasts", [])

        if not forecasts:
            return "Прогнозы отсутствуют."

        bullish = sum(item["direction"] == "UP" for item in forecasts)
        bearish = sum(item["direction"] == "DOWN" for item in forecasts)
        uncertain = len(forecasts) - bullish - bearish

        return (
            f"Горизонты роста: {bullish}; снижения: {bearish}; "
            f"бокового или неопределённого движения: {uncertain}."
        )

    @staticmethod
    def _news_summary(news: dict[str, Any]) -> str:
        articles = news.get("articles", [])

        if not articles:
            return "Свежие связанные новости не найдены."

        positive = sum(item.get("sentiment") == "positive" for item in articles)
        negative = sum(item.get("sentiment") == "negative" for item in articles)
        neutral = len(articles) - positive - negative

        return (
            f"Найдено новостей: {len(articles)}. "
            f"Позитивных: {positive}, негативных: {negative}, "
            f"нейтральных: {neutral}."
        )

    def _build_answer(
        self,
        *,
        asset: str,
        recommendation: str,
        confidence: int,
        market_view: str,
        risk: str,
        signal: dict[str, Any] | None,
        forecast: dict[str, Any] | None,
        news: dict[str, Any] | None,
        available_sources: int,
    ) -> str:
        recommendation_text = {
            "BUY": "покупка выглядит привлекательной",
            "CAUTIOUS_BUY": "возможна осторожная частичная покупка",
            "WAIT": "лучше дождаться более сильного подтверждения",
            "CAUTIOUS_SELL": "ситуация выглядит умеренно негативной",
            "AVOID_OR_REDUCE": "покупка сейчас выглядит слишком рискованной",
        }[recommendation]

        parts = [
            f"По текущим данным для {asset} {recommendation_text}.",
            f"Итоговый режим: {market_view}.",
            f"Уверенность анализа: {confidence}%.",
            f"Уровень риска: {risk}.",
            f"Доступно аналитических источников: {available_sources} из 3.",
        ]

        if signal:
            decision = signal["decision"]
            parts.append(
                f"Технический сигнал: {decision['action']} "
                f"с уверенностью {decision['confidence']:.0f}%."
            )

            levels = decision.get("levels")
            if levels:
                parts.append(
                    "Расчётные уровни: "
                    f"вход {float(levels['entry']):.2f}, "
                    f"стоп {float(levels['stop_loss']):.2f}, "
                    f"цель {float(levels['take_profit']):.2f}."
                )

        if forecast and forecast.get("forecasts"):
            day_forecast = next(
                (
                    item
                    for item in forecast["forecasts"]
                    if item["horizon_minutes"] == 1440
                ),
                forecast["forecasts"][0],
            )

            parts.append(
                "Прогноз на выбранном ключевом горизонте: "
                f"{day_forecast['direction']}, "
                f"уверенность {day_forecast['confidence']}%, "
                f"ожидаемое изменение "
                f"{day_forecast['expected_change_percent']:.2f}%."
            )

        if news:
            parts.append(self._news_summary(news))

        parts.append(
            "Не открывайте позицию только на основании одного результата; "
            "учитывайте горизонт, размер позиции и допустимую просадку."
        )

        return " ".join(parts)

    @staticmethod
    def _unsupported_response(
        asset: str,
        request: AssistantChatRequest,
    ) -> AssistantChatResponse:
        return AssistantChatResponse(
            intent="asset_analysis",
            answer=(
                f"Актив {asset} пока не поддерживается модулем реального анализа. "
                "На этом этапе доступны BTC, ETH, BNB, SOL, XRP, ADA, DOGE, "
                "TRX, AVAX и LINK."
            ),
            confidence=20,
            risk=request.context.risk_level,
            market_view="neutral",
            follow_up_questions=[
                "Выберите один из поддерживаемых криптоактивов.",
            ],
            details={
                "asset": asset,
                "status": "unsupported",
            },
            disclaimer=DISCLAIMER,
        )

    @staticmethod
    def _unavailable_response(
        asset: str,
        request: AssistantChatRequest,
    ) -> AssistantChatResponse:
        return AssistantChatResponse(
            intent="asset_analysis",
            answer=(
                f"Не удалось загрузить рыночные данные для {asset}. "
                "Рекомендация не сформирована, чтобы не выдавать неподтверждённый вывод."
            ),
            confidence=0,
            risk=request.context.risk_level,
            market_view="neutral",
            details={
                "asset": asset,
                "status": "data_unavailable",
            },
            disclaimer=DISCLAIMER,
        )
