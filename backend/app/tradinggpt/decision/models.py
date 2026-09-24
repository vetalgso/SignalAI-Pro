from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


FinalDecisionStatus = Literal[
    "EXECUTE",
    "EXECUTE_REDUCED",
    "REJECT",
    "NO_TRADE",
]


@dataclass(frozen=True, slots=True)
class FinalTradeDecision:
    status: FinalDecisionStatus
    symbol: str | None
    side: str
    recommendation: str

    approved_quantity: float
    approved_value: float
    approved_risk: float

    conviction_score: float
    execution_ready: bool
    risk_allowed: bool

    summary: str
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def executable(self) -> bool:
        return self.status in {
            "EXECUTE",
            "EXECUTE_REDUCED",
        }

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["executable"] = self.executable
        payload["approved_quantity"] = round(
            self.approved_quantity,
            8,
        )
        payload["approved_value"] = round(
            self.approved_value,
            2,
        )
        payload["approved_risk"] = round(
            self.approved_risk,
            2,
        )
        payload["conviction_score"] = round(
            self.conviction_score,
            2,
        )
        payload["reasons"] = list(self.reasons)
        payload["warnings"] = list(self.warnings)
        return payload
