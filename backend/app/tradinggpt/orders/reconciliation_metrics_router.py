from __future__ import annotations

from fastapi import (
    APIRouter,
    Response,
    status,
)

from app.core.config import settings

from .reconciliation_background import (
    order_reconciliation_background_loop,
)
from .reconciliation_metrics import (
    PROMETHEUS_CONTENT_TYPE,
    OrderReconciliationMetricsService,
)


router = APIRouter(
    prefix="/orders/reconciliation",
    tags=["order-reconciliation"],
)


@router.get(
    "/metrics",
    response_class=Response,
    responses={
        status.HTTP_200_OK: {
            "description": (
                "Prometheus automatic order "
                "reconciliation metrics."
            ),
            "content": {
                "text/plain": {
                    "schema": {
                        "type": "string",
                    },
                },
            },
        },
    },
)
def get_order_reconciliation_metrics(
) -> Response:
    metrics = OrderReconciliationMetricsService(
        enabled=(
            settings
            .order_reconciliation_background_enabled
        ),
        batch_size=(
            settings
            .order_reconciliation_batch_size
        ),
        status_provider=(
            order_reconciliation_background_loop
            .status
        ),
    ).render()

    return Response(
        content=metrics,
        media_type=PROMETHEUS_CONTENT_TYPE,
    )
