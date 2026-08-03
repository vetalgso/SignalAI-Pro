from __future__ import annotations

from typing import Any

from .payload_repository import (
    SchedulerPayloadRepository,
)
from .schemas import SafeSchedulerCycleRequest


class SchedulerPayloadService:
    def __init__(
        self,
        repository: SchedulerPayloadRepository,
    ) -> None:
        self._repository = repository

    def get(self) -> dict[str, object]:
        return self.serialize(
            self._repository.get_or_create()
        )

    def save(
        self,
        *,
        runtime_risk_payload: dict[str, Any],
        analysis_payload: dict[str, Any],
    ) -> dict[str, object]:
        validated = (
            SafeSchedulerCycleRequest
            .model_validate(
                {
                    "runtime_risk": (
                        runtime_risk_payload
                    ),
                    "analysis": analysis_payload,
                }
            )
        )

        stored = self._repository.save(
            runtime_risk_payload=(
                validated.runtime_risk.model_dump(
                    mode="json"
                )
            ),
            analysis_payload=(
                validated.analysis.model_dump(
                    mode="json"
                )
            ),
        )

        return self.serialize(stored)

    def clear(self) -> dict[str, object]:
        return self.serialize(
            self._repository.clear()
        )

    @staticmethod
    def serialize(
        payload: object,
    ) -> dict[str, object]:
        return {
            "configured": payload.configured,
            "runtime_risk_payload": (
                payload.runtime_risk_payload
            ),
            "analysis_payload": (
                payload.analysis_payload
            ),
            "updated_at": payload.updated_at,
        }
