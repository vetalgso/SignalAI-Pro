from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TradingExplanation:
    summary: str
    thesis: str
    risk_level: str
    pros: tuple[str, ...]
    cons: tuple[str, ...]
    risks: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "thesis": self.thesis,
            "risk_level": self.risk_level,
            "pros": list(self.pros),
            "cons": list(self.cons),
            "risks": list(self.risks),
        }
