"""Public, bounded facts about a news response; no provider error strings."""
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, ValidationError, model_validator


class NewsDiagnostics(BaseModel):
    version: Literal[1] = 1
    observed_at: AwareDatetime
    coverage: Literal["ALL", "SUPPORTED", "UNSUPPORTED"]
    sources_state: Literal["COMPLETE", "PARTIAL", "FAILED"]
    total_sources: int = Field(gt=0)
    failed_sources: int = Field(ge=0)
    collected_articles: int = Field(ge=0)
    matched_articles: int = Field(ge=0)

    @model_validator(mode="after")
    def consistent(self):
        if self.failed_sources > self.total_sources or self.matched_articles > self.collected_articles:
            raise ValueError("Inconsistent news counts")
        expected = ("FAILED" if self.failed_sources == self.total_sources else
                    "PARTIAL" if self.failed_sources else "COMPLETE")
        if self.sources_state != expected:
            raise ValueError("Inconsistent source status")
        if self.coverage == "UNSUPPORTED" and self.matched_articles:
            raise ValueError("Unsupported asset has matches")
        if self.sources_state == "FAILED" and self.collected_articles:
            raise ValueError("Failed collection has articles")
        return self


def read_news_diagnostics(raw: object) -> NewsDiagnostics | None:
    if not isinstance(raw, dict) or raw.get("version") != 1:
        return None
    try:
        return NewsDiagnostics.model_validate(raw)
    except ValidationError:
        return None
