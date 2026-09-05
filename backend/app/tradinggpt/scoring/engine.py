from __future__ import annotations

from typing import Any

from app.tradinggpt.scoring.models import ScoringResult, TradeDirection


class ScoringEngine:
    """
    Centralized TradingGPT scoring logic.

    score:
        0 = strong SHORT
        50 = neutral
        100 = strong LONG

    opportunity_score:
        0 = no actionable edge
        100 = strong directional opportunity

    confidence:
        Reliability of the combined evidence before quality penalties.
    """

    SIGNAL_WEIGHT = 0.45
    FORECAST_WEIGHT = 0.40
    NEWS_WEIGHT = 0.15

    TIMEFRAME_WEIGHTS = {
        15: 0.10,
        60: 0.20,
        240: 0.30,
        1440: 0.40,
    }

    TIMEFRAME_LABELS = {
        15: "15m",
        60: "1H",
        240: "4H",
        1440: "1D",
    }

    @staticmethod
    def signal_score(signal: dict[str, Any] | None) -> float:
        if not signal:
            return 50.0

        decision = signal["decision"]
        action = decision["action"]
        confidence = float(decision["confidence"])

        if action == "LONG":
            return max(0.0, min(100.0, 50 + confidence / 2))

        if action == "SHORT":
            return max(0.0, min(100.0, 50 - confidence / 2))

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
            probabilities = item.get("probabilities", {})

            up = float(probabilities.get("up", 0.0))
            down = float(probabilities.get("down", 0.0))

            directional_score = 50 + up * 50 - down * 50

            horizon = int(item.get("horizon_minutes", 0))

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
    def trade_direction(
        score: float,
        *,
        neutral_band: float = 8.0,
    ) -> TradeDirection:
        if score >= 50 + neutral_band:
            return "LONG"

        if score <= 50 - neutral_band:
            return "SHORT"

        return "NEUTRAL"

    @staticmethod
    def source_direction(
        score: float,
        *,
        neutral_band: float = 8.0,
    ) -> TradeDirection:
        return ScoringEngine.trade_direction(
            score,
            neutral_band=neutral_band,
        )

    @classmethod
    def consensus_score(
        cls,
        *,
        combined_direction: TradeDirection,
        signal_score: float,
        forecast_score: float,
        news_score: float,
        signal_available: bool,
        forecast_available: bool,
        news_available: bool,
    ) -> float:
        """
        Measures weighted directional agreement between available sources.

        100:
            all directional sources agree with the final direction.

        50:
            neutral evidence or no directional evidence.

        0:
            all directional sources oppose the final direction.
        """
        if combined_direction == "NEUTRAL":
            return 50.0

        sources = (
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
        )

        agreeing_weight = 0.0
        opposing_weight = 0.0
        directional_weight = 0.0

        for source_score, weight, available in sources:
            if not available:
                continue

            source_direction = cls.source_direction(source_score)

            if source_direction == "NEUTRAL":
                continue

            directional_weight += weight

            if source_direction == combined_direction:
                agreeing_weight += weight
            else:
                opposing_weight += weight

        if directional_weight == 0:
            return 50.0

        consensus = (
            50.0
            + agreeing_weight / directional_weight * 50.0
            - opposing_weight / directional_weight * 50.0
        )

        return max(0.0, min(100.0, consensus))

    @staticmethod
    def opportunity_score(
        score: float,
        confidence: int,
        consensus_score: float = 50.0,
    ) -> float:
        """
        Measures actionable directional strength independently of LONG/SHORT.

        Directional strength:
            score 50 -> 0
            score 0/100 -> 100

        Confidence scales the directional edge so weakly confirmed extremes do
        not automatically become high-quality opportunities.
        """
        directional_strength = min(
            100.0,
            abs(score - 50.0) * 2,
        )

        confidence_factor = max(
            0.0,
            min(1.0, confidence / 100),
        )

        consensus_factor = max(
            0.0,
            min(1.0, consensus_score / 100),
        )

        reliability_factor = (
            0.25
            + confidence_factor * 0.50
            + consensus_factor * 0.25
        )

        opportunity = directional_strength * reliability_factor

        return max(0.0, min(100.0, opportunity))

    @classmethod
    def timeframe_analysis(
        cls,
        forecast: dict[str, Any] | None,
        trade_direction: TradeDirection = "NEUTRAL",
    ) -> dict[str, Any]:
        """
        Builds a normalized multi-timeframe market view.

        Supported horizons:
            15m, 1H, 4H, 1D

        timeframe_consensus_score:
            100 = all supported horizons match the trade
            50 = neutral or insufficient evidence
            0 = all supported horizons oppose the trade
        """
        result: dict[str, Any] = {
            "directions": {},
            "scores": {},
            "timeframe_consensus_score": 50.0,
            "trend_direction": "NEUTRAL",
            "trade_style": "NEUTRAL",
            "reasons": [],
        }

        if not forecast:
            result["reasons"].append(
                "Multi-timeframe forecast data is unavailable."
            )
            return result

        items = forecast.get("forecasts", [])

        if not items:
            result["reasons"].append(
                "Multi-timeframe forecast horizons are unavailable."
            )
            return result

        weighted_long = 0.0
        weighted_short = 0.0
        directional_weight = 0.0
        supported_weight = 0.0

        for item in items:
            try:
                horizon = int(item.get("horizon_minutes", 0))
            except (TypeError, ValueError):
                continue

            if horizon not in cls.TIMEFRAME_WEIGHTS:
                continue

            probabilities = item.get("probabilities", {})
            up = float(probabilities.get("up", 0.0) or 0.0)
            down = float(probabilities.get("down", 0.0) or 0.0)

            directional_score = max(
                0.0,
                min(100.0, 50.0 + up * 50.0 - down * 50.0),
            )

            direction = cls.trade_direction(
                directional_score,
                neutral_band=5.0,
            )

            label = cls.TIMEFRAME_LABELS[horizon]
            weight = cls.TIMEFRAME_WEIGHTS[horizon]

            result["directions"][label] = direction
            result["scores"][label] = round(directional_score, 2)
            supported_weight += weight

            if direction == "LONG":
                weighted_long += weight
                directional_weight += weight
            elif direction == "SHORT":
                weighted_short += weight
                directional_weight += weight

        directions = result["directions"]

        if not directions:
            result["reasons"].append(
                "Supported forecast horizons are unavailable."
            )
            return result

        if supported_weight > 0:
            if trade_direction == "LONG":
                matching_weight = weighted_long
                opposing_weight = weighted_short
            elif trade_direction == "SHORT":
                matching_weight = weighted_short
                opposing_weight = weighted_long
            else:
                matching_weight = max(
                    weighted_long,
                    weighted_short,
                )
                opposing_weight = min(
                    weighted_long,
                    weighted_short,
                )

            consensus = (
                50.0
                + (
                    matching_weight - opposing_weight
                ) / supported_weight * 50.0
            )

            result["timeframe_consensus_score"] = round(
                max(0.0, min(100.0, consensus)),
                2,
            )

        long_term_direction = directions.get("1D")
        medium_term_direction = directions.get("4H")

        if (
            long_term_direction
            and long_term_direction != "NEUTRAL"
        ):
            trend_direction = long_term_direction
        elif (
            medium_term_direction
            and medium_term_direction != "NEUTRAL"
        ):
            trend_direction = medium_term_direction
        elif weighted_long > weighted_short:
            trend_direction = "LONG"
        elif weighted_short > weighted_long:
            trend_direction = "SHORT"
        else:
            trend_direction = "NEUTRAL"

        result["trend_direction"] = trend_direction

        if trade_direction == "NEUTRAL":
            trade_style = "NEUTRAL"
        elif trend_direction == "NEUTRAL":
            trade_style = "MIXED"
        elif trade_direction == trend_direction:
            trade_style = "TREND_FOLLOWING"
        else:
            trade_style = "COUNTER_TREND"

        result["trade_style"] = trade_style

        for label in ("15m", "1H", "4H", "1D"):
            direction = directions.get(label)

            if direction:
                result["reasons"].append(
                    f"Forecast {label}: {direction}."
                )

        result["reasons"].append(
            "Timeframe alignment: "
            f"{result['timeframe_consensus_score']:.0f}%."
        )

        if trend_direction != "NEUTRAL":
            result["reasons"].append(
                f"Primary trend: {trend_direction}."
            )

        if trade_style != "NEUTRAL":
            result["reasons"].append(
                f"Trade style: {trade_style}."
            )

        return result

    @staticmethod
    def explanation_reasons(
        *,
        signal: dict[str, Any] | None,
        news: dict[str, Any] | None,
        trade_direction: TradeDirection,
        consensus_score: float,
        timeframe_analysis: dict[str, Any],
        risk: str,
    ) -> list[str]:
        reasons: list[str] = []

        if signal:
            decision = signal.get("decision", {})
            action = decision.get("action")
            signal_confidence = decision.get("confidence")

            if action:
                if signal_confidence is None:
                    reasons.append(f"Signal Engine: {action}.")
                else:
                    reasons.append(
                        "Signal Engine: "
                        f"{action} ({float(signal_confidence):.0f}%)."
                    )

        reasons.extend(timeframe_analysis.get("reasons", []))

        if news and news.get("articles"):
            sentiment_counts = {
                "positive": 0,
                "neutral": 0,
                "negative": 0,
            }

            for article in news["articles"]:
                sentiment = article.get("sentiment", "neutral")

                if sentiment in sentiment_counts:
                    sentiment_counts[sentiment] += 1

            dominant_sentiment = max(
                sentiment_counts,
                key=sentiment_counts.get,
            )

            reasons.append(
                f"News sentiment: {dominant_sentiment.upper()}."
            )

        reasons.append(
            f"Source consensus: {consensus_score:.0f}%."
        )
        reasons.append(f"Final direction: {trade_direction}.")
        reasons.append(f"Risk level: {risk.upper()}.")

        return reasons

    @staticmethod
    def ranking_score(
        opportunity_score: float,
        consensus_score: float,
        confidence: int,
        timeframe_consensus_score: float | None = None,
    ) -> float:
        """
        Produces a unified market-ranking score.

        Ranking v2 compatibility:
            when timeframe_consensus_score is omitted, the original
            opportunity/consensus/confidence formula is preserved.

        Ranking v3:
            timeframe alignment becomes an explicit reliability factor.
        """
        normalized_opportunity = max(
            0.0,
            min(100.0, opportunity_score),
        )
        normalized_consensus = max(
            0.0,
            min(100.0, consensus_score),
        )
        normalized_confidence = max(
            0,
            min(100, confidence),
        )

        if timeframe_consensus_score is None:
            ranking = (
                normalized_opportunity * 0.60
                + normalized_consensus * 0.25
                + normalized_confidence * 0.15
            )
        else:
            normalized_timeframe_consensus = max(
                0.0,
                min(100.0, timeframe_consensus_score),
            )

            ranking = (
                normalized_opportunity * 0.50
                + normalized_consensus * 0.20
                + normalized_timeframe_consensus * 0.20
                + normalized_confidence * 0.10
            )

        return max(0.0, min(100.0, ranking))

    @staticmethod
    def recommendation(
        score: float,
        confidence: int,
        opportunity_score: float | None = None,
    ) -> str:
        opportunity = (
            ScoringEngine.opportunity_score(score, confidence)
            if opportunity_score is None
            else opportunity_score
        )

        if confidence < 35:
            return "WAIT"

        direction = ScoringEngine.trade_direction(score)

        if direction == "NEUTRAL":
            return "WAIT"

        if opportunity >= 68:
            return direction

        if opportunity >= 48:
            return (
                "CAUTIOUS_BUY"
                if direction == "LONG"
                else "CAUTIOUS_SHORT"
            )

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

        direction = cls.trade_direction(score)

        consensus = cls.consensus_score(
            combined_direction=direction,
            signal_score=signal_score,
            forecast_score=forecast_score,
            news_score=news_score,
            signal_available=signal is not None,
            forecast_available=forecast is not None,
            news_available=news is not None,
        )

        opportunity = cls.opportunity_score(
            score,
            confidence,
            consensus,
        )

        return ScoringResult(
            score=score,
            opportunity_score=opportunity,
            consensus_score=consensus,
            confidence=confidence,
            trade_direction=direction,
            signal_score=signal_score,
            forecast_score=forecast_score,
            news_score=news_score,
        )
