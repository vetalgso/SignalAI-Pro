from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any

from .quality_details import QualityBreakdown


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

        indicators = signal.get("indicators")
        if not isinstance(indicators, dict):
            return 10

        volume = indicators.get("volume")
        if not isinstance(volume, dict):
            return 10

        raw_ratio = volume.get("ratio")

        try:
            volume_ratio = float(raw_ratio)
        except (TypeError, ValueError):
            return 10

        if volume_ratio != volume_ratio:
            return 10

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
        details = cls.quality_breakdown(signal=signal, forecast=forecast, news=news)
        return details.total, cls.quality_warnings(details)

    @classmethod
    def quality_breakdown(
        cls, *, signal: dict[str, Any] | None,
        forecast: dict[str, Any] | None, news: dict[str, Any] | None,
    ) -> QualityBreakdown:
        # These are the existing scoring functions; diagnostic fields do not
        # reinterpret directions, change thresholds or alter the cap.
        forecast_points = cls.uncertainty_penalty(forecast)
        volume_points = cls.volume_penalty(signal)
        news_points = cls.news_verification_penalty(news)
        items = (forecast.get("forecasts") or []) if forecast else []
        horizons = []
        for item in items:
            try:
                horizon = int(item.get("horizon_minutes", 0))
            except (TypeError, ValueError, OverflowError):
                horizon = 0
            direction = item.get("direction")
            horizons.append({
                "horizon_minutes": horizon if horizon > 0 else None,
                "direction": direction if direction in {"UP", "DOWN", "SIDEWAYS", "UNCERTAIN"} else "UNKNOWN",
            })

        indicators = signal.get("indicators") if signal else None
        volume = indicators.get("volume") if isinstance(indicators, dict) else None
        raw_ratio = volume.get("ratio") if isinstance(volume, dict) else None
        ratio = None
        volume_state = "MISSING" if raw_ratio is None else "INVALID"
        try:
            number = float(raw_ratio)
            if isfinite(number):
                ratio, volume_state = number, "AVAILABLE"
        except (TypeError, ValueError, OverflowError):
            pass

        articles = (news.get("articles") or []) if news else []
        total = forecast_points + volume_points + news_points
        return QualityBreakdown(
            calculated_at=datetime.now(timezone.utc),
            forecast={
                "points": forecast_points,
                "state": "AVAILABLE" if items else "MISSING",
                "uncertain_count": sum(h["direction"] in {"UNCERTAIN", "SIDEWAYS"} for h in horizons),
                "horizons": horizons,
            },
            volume={"points": volume_points, "state": volume_state, "ratio": ratio},
            news={
                "points": news_points, "state": "AVAILABLE" if articles else "MISSING",
                "article_count": len(articles),
                "unverified_count": sum(a.get("status") != "verified" for a in articles),
            },
            uncapped_total=total, total=min(total, 30),
        )

    @staticmethod
    def quality_warnings(details: QualityBreakdown) -> list[str]:
        warnings = []
        forecast, volume, news = details.forecast, details.volume, details.news
        if forecast.state == "MISSING":
            warnings.append("Данные прогнозных горизонтов отсутствуют.")
        elif forecast.points > 0:
            warnings.append(
                f"Неопределённые или боковые прогнозы: {forecast.uncertain_count} из {len(forecast.horizons)} горизонтов."
            )
        if volume.state == "MISSING":
            warnings.append("Данные об отношении объёма к среднему отсутствуют.")
        elif volume.state == "INVALID":
            warnings.append("Данные об отношении объёма к среднему некорректны.")
        elif volume.points > 0:
            warnings.append(f"Отношение текущего объёма к среднему: {volume.ratio:.3f}.")
        if news.state == "MISSING":
            warnings.append("Данные новостей отсутствуют или список новостей пуст.")
        elif news.points > 0:
            warnings.append(f"Новости без статуса verified: {news.unverified_count} из {news.article_count}.")
        return warnings
