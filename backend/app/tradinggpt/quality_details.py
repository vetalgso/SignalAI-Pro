"""Safe, versioned facts captured when a quality penalty is calculated."""
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, FiniteFloat, ValidationError, model_validator


class ForecastHorizon(BaseModel):
    horizon_minutes: int | None = Field(default=None, gt=0)
    direction: Literal["UP", "DOWN", "SIDEWAYS", "UNCERTAIN", "UNKNOWN"]


class ForecastQuality(BaseModel):
    points: int = Field(ge=0, le=15)
    state: Literal["AVAILABLE", "MISSING"]
    uncertain_count: int = Field(ge=0)
    horizons: list[ForecastHorizon]


class VolumeQuality(BaseModel):
    points: int = Field(ge=0, le=15)
    state: Literal["AVAILABLE", "MISSING", "INVALID"]
    ratio: FiniteFloat | None


class NewsQuality(BaseModel):
    points: int = Field(ge=0, le=10)
    state: Literal["AVAILABLE", "MISSING"]
    article_count: int = Field(ge=0)
    unverified_count: int = Field(ge=0)


class QualityBreakdown(BaseModel):
    version: Literal[1] = 1
    calculated_at: AwareDatetime
    forecast: ForecastQuality
    volume: VolumeQuality
    news: NewsQuality
    uncapped_total: int = Field(ge=0, le=40)
    cap: Literal[30] = 30
    total: int = Field(ge=0, le=30)

    @model_validator(mode="after")
    def consistent_facts(self):
        if self.uncapped_total != self.forecast.points + self.volume.points + self.news.points:
            raise ValueError("Inconsistent quality components")
        if self.total != min(self.uncapped_total, self.cap):
            raise ValueError("Inconsistent quality total")
        uncertain = sum(h.direction in {"UNCERTAIN", "SIDEWAYS"} for h in self.forecast.horizons)
        if self.forecast.uncertain_count != uncertain:
            raise ValueError("Inconsistent forecast counts")
        if (self.forecast.state == "MISSING") != (len(self.forecast.horizons) == 0):
            raise ValueError("Inconsistent forecast availability")
        if (self.volume.state == "AVAILABLE") != (self.volume.ratio is not None):
            raise ValueError("Inconsistent volume availability")
        if self.news.unverified_count > self.news.article_count:
            raise ValueError("Inconsistent news counts")
        if (self.news.state == "MISSING") != (self.news.article_count == 0):
            raise ValueError("Inconsistent news availability")
        return self


def read_quality_breakdown(snapshot: object) -> QualityBreakdown | None:
    if not isinstance(snapshot, dict):
        return None
    raw = snapshot.get("quality_breakdown")
    if not isinstance(raw, dict) or raw.get("version") != 1:
        return None
    try:
        result = QualityBreakdown.model_validate(raw)
    except ValidationError:
        return None
    # Never attach inconsistent details to a candidate's saved penalty.
    if result.total != snapshot.get("quality_penalty"):
        return None
    return result
