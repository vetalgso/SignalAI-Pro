from __future__ import annotations

from typing import Any

from app.tradinggpt.scoring.models import ScoringResult


class ScoringEngine:
    """
    Centralized TradingGPT scoring logic.

    Current formulas intentionally preserve the behavior that previously lived
    in CryptoAssetAnalysisModule. This allows the scoring implementation to be
    improved later without coupling it to orchestration and response building.
    """

    SIGNAL_WEIGHT = 0.45
    FORECAST_WEIGHT = 0.40
    NEWS_WEIGHT = 0.15

    @staticmethod
    def signal_score(signal: dict[str, Any] | None) -> float:
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

        return max(
            0.0,
            min(
                100.0,
                50 + (long_score - short_score) / 2,
            ),
        )

    @staticmethod
    def forecast_score(forecast: dict[str, Any] | None) -> float:
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

        if total_weight == 0:
            return 50.0

        return max(
            0.0,
            min(
                100.0,
                weighted_total / total_weight,
            ),
        )

    @staticmethod
    def news_score(news: dict[str, Any] | None) -> float:
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

            weight = max(
                1.0,
                float(article.get("impact_score", 50)),
            )

            weighted_sentiment += sentiment_value * weight
            total_weight += weight

        normalized = (
            weighted_sentiment / total_weight
            if total_weight
            else 0.0
        )

        return max(
            0.0,
            min(
                100.0,
                50 + normalized * 50,
            ),
        )

    @classmethod
    def combined_score(
        cls,
        *,
        signal_score: float,
        forecast_score: float,
        news_score: float,
        signal_available: bool,
        forecast_available: bool,
        news_available: bool,
    ) -> tuple[float, int]:
        sources = [
            (
                signal_score,
                cls.SIGNAL_WEIGHT,
                signal_available,
            ),
            (
                forecast_score,
                cls.FORECAST_WEIGHT,
                forecast_available,
            ),
            (
                news_score,
                cls.NEWS_WEIGHT,
                news_available,
            ),
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

        confidence = round(
            min(
                95,
                distance_from_neutral * 0.65
                + coverage * 35,
            )
        )

        return combined, max(20, confidence)

    @staticmethod
    def recommendation(
        score: float,
        confidence: int,
    ) -> str:
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

    @classmethod
    def evaluate(
        cls,
        *,
        signal: dict[str, Any] | None,
        forecast: dict[str, Any] | None,
        news: dict[str, Any] | None,
    ) -> ScoringResult:
        signal_score = cls.signal_score(signal)
        forecast_score = cls.forecast_score(forecast)
        news_score = cls.news_score(news)

        score, confidence = cls.combined_score(
            signal_score=signal_score,
            forecast_score=forecast_score,
            news_score=news_score,
            signal_available=signal is not None,
            forecast_available=forecast is not None,
            news_available=news is not None,
        )

        return ScoringResult(
            score=score,
            confidence=confidence,
            signal_score=signal_score,
            forecast_score=forecast_score,
            news_score=news_score,
        )
