from __future__ import annotations

import hashlib
import json

from app.tradinggpt.engine.models import (
    TradingGPTAnalysisResult,
)
from app.tradinggpt.orders.journal_service import (
    JournaledOrderService,
)
from app.tradinggpt.orders.schemas import (
    JournalOrderExecuteRequest,
)


class AnalyzeAndExecuteService:
    """
    Connect a deterministic TradingGPT analysis result
    to journaled order execution.

    Safety rules:
    - NO_TRADE and REJECT are never executed;
    - missing decisions or order intents are skipped;
    - dry-run is enabled by default at the API layer;
    - generated idempotency keys are deterministic.
    """

    def __init__(
        self,
        *,
        journal_service: JournaledOrderService,
    ) -> None:
        self._journal_service = journal_service

    def execute(
        self,
        *,
        analysis: TradingGPTAnalysisResult,
        dry_run: bool,
        idempotency_key: str | None = None,
    ) -> dict[str, object]:
        analysis_payload = analysis.to_dict()
        decision = analysis.decision
        order_intent = analysis.order_intent

        if decision is None:
            return self._skipped(
                analysis_payload=analysis_payload,
                reason="Analysis did not produce a final decision.",
            )

        if not decision.executable:
            return self._skipped(
                analysis_payload=analysis_payload,
                reason=(
                    "Final decision does not permit execution: "
                    f"{decision.status}."
                ),
            )

        if not decision.execution_ready:
            return self._skipped(
                analysis_payload=analysis_payload,
                reason="Final decision is not execution-ready.",
            )

        if not decision.risk_allowed:
            return self._skipped(
                analysis_payload=analysis_payload,
                reason="Risk engine did not allow execution.",
            )

        if order_intent is None:
            return self._skipped(
                analysis_payload=analysis_payload,
                reason="Executable decision has no order intent.",
            )

        resolved_key = (
            idempotency_key
            or self._build_idempotency_key(
                analysis=analysis,
            )
        )

        journal_request = JournalOrderExecuteRequest(
            **order_intent.to_dict(),
            idempotency_key=resolved_key,
            dry_run=dry_run,
        )

        journal = self._journal_service.execute(
            journal_request
        )

        if bool(journal.get("replayed")):
            action = "REPLAYED"
        elif dry_run:
            action = "DRY_RUN"
        else:
            action = "EXECUTED"

        return {
            "action": action,
            "reason": None,
            "analysis": analysis_payload,
            "journal": journal,
        }

    @staticmethod
    def _build_idempotency_key(
        *,
        analysis: TradingGPTAnalysisResult,
    ) -> str:
        decision_payload = (
            analysis.decision.to_dict()
            if analysis.decision is not None
            else None
        )
        order_payload = (
            analysis.order_intent.to_dict()
            if analysis.order_intent is not None
            else None
        )

        canonical_payload = json.dumps(
            {
                "decision": decision_payload,
                "order_intent": order_payload,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )

        digest = hashlib.sha256(
            canonical_payload.encode("utf-8")
        ).hexdigest()

        return f"analysis-{digest}"

    @staticmethod
    def _skipped(
        *,
        analysis_payload: dict[str, object],
        reason: str,
    ) -> dict[str, object]:
        return {
            "action": "SKIPPED",
            "reason": reason,
            "analysis": analysis_payload,
            "journal": None,
        }
