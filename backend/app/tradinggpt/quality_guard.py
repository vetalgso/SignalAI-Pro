from __future__ import annotations

from typing import Any


class AnalysisQualityGuard:
    @staticmethod
    def uncertainty_penalty(forecast: dict[str, Any] | None) -> int:
        if not forecast:
            return 15

        items = forecast.get("forecasts", [])
        if not items:
            return 15

        uncertain_count = sum(
            item.get("direction") in {"UNCERTAIN", "SIDEWAYS"}
            for item in items
        )

        ratio = uncertain_count / len(items)

        if ratio >= 0.75:
            return 15

        if ratio >= 0.5:
            return 10

        if ratio >= 0.25:
            return 5

        return 0

    @staticmethod
    def volume_penalty(signal: dict[str, Any] | None) -> int:
        if not signal:
            return 10

        volume_ratio = float(
            signal.get("indicators", {})
            .get("volume", {})
            .get("ratio", 1)
        )

        if volume_ratio < 0.25:
            return 15

        if volume_ratio < 0.5:
            return 10

        if volume_ratio < 0.8:
            return 5

        return 0

    @staticmethod
    def news_verification_penalty(news: dict[str, Any] | None) -> int:
        if not news:
            return 5

        articles = news.get("articles", [])
        if not articles:
            return 5

        unverified_count = sum(
            article.get("status") != "verified"
            for article in articles
        )

        ratio = unverified_count / len(articles)

        if ratio >= 0.8:
            return 10

        if ratio >= 0.5:
            return 5

        return 0

    @classmethod
    def confidence_penalty(
        cls,
        *,
        signal: dict[str, Any] | None,
        forecast: dict[str, Any] | None,
        news: dict[str, Any] | None,
    ) -> tuple[int, list[str]]:
        penalties: list[tuple[int, str]] = [
            (
                cls.uncertainty_penalty(forecast),
                "Большинство прогнозных горизонтов неопределённые.",
            ),
            (
                cls.volume_penalty(signal),
                "Текущий объём значительно ниже среднего.",
            ),
            (
                cls.news_verification_penalty(news),
                "Большинство новостей не подтверждено дополнительными источниками.",
            ),
        ]

        total = sum(value for value, _ in penalties)
        reasons = [reason for value, reason in penalties if value > 0]

        return min(total, 30), reasons
