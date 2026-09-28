from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.scheduler_payload import (
    SchedulerPayload,
)


class SchedulerPayloadRepository:
    PAYLOAD_ID = 1

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def get_or_create(self) -> SchedulerPayload:
        payload = self._session.get(
            SchedulerPayload,
            self.PAYLOAD_ID,
        )

        if payload is not None:
            return payload

        payload = SchedulerPayload(
            id=self.PAYLOAD_ID,
            configured=False,
        )

        self._session.add(payload)
        self._session.commit()
        self._session.refresh(payload)

        return payload

    def save(
        self,
        *,
        runtime_risk_payload: dict[str, Any],
        analysis_payload: dict[str, Any],
    ) -> SchedulerPayload:
        payload = self.get_or_create()

        payload.configured = True
        payload.runtime_risk_payload = (
            runtime_risk_payload
        )
        payload.analysis_payload = analysis_payload
        payload.updated_at = datetime.now(
            timezone.utc
        )

        self._session.add(payload)
        self._session.commit()
        self._session.refresh(payload)

        return payload

    def clear(self) -> SchedulerPayload:
        payload = self.get_or_create()

        payload.configured = False
        payload.runtime_risk_payload = None
        payload.analysis_payload = None
        payload.updated_at = datetime.now(
            timezone.utc
        )

        self._session.add(payload)
        self._session.commit()
        self._session.refresh(payload)

        return payload
