from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.tradinggpt.risk.models import (
    AccountRiskContext,
    RiskLimits,
)
from app.tradinggpt.risk.runtime import (
    RuntimeRiskGuard,
)


class SafeSchedulerCycleService:
    """
    Run one guarded trading cycle.

    Safety guarantees:
    - runtime account risk is checked first;
    - a denied cycle never invokes analysis/execution;
    - the execution callback is always called with
      dry_run=True;
    - this service does not create a background task.
    """

    def __init__(
        self,
        *,
        execute_callback: Callable[
            [bool],
            dict[str, Any],
        ],
    ) -> None:
        self._execute_callback = execute_callback

    def run(
        self,
        *,
        account: AccountRiskContext,
        limits: RiskLimits | None = None,
    ) -> dict[str, object]:
        risk_decision = RuntimeRiskGuard.evaluate(
            account=account,
            limits=limits,
        )
        risk_payload = risk_decision.to_dict()

        if not risk_decision.trading_allowed:
            return {
                "status": "BLOCKED",
                "dry_run": True,
                "risk": risk_payload,
                "execution": None,
                "reason": (
                    "Scheduler cycle was blocked by "
                    "the runtime risk guard."
                ),
            }

        execution = self._execute_callback(True)

        return {
            "status": "COMPLETED",
            "dry_run": True,
            "risk": risk_payload,
            "execution": execution,
            "reason": None,
        }
