from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import (
    SessionLocal,
    engine,
)
from app.tradinggpt.exchange_accounts.crypto import (
    CredentialCipher,
)
from app.tradinggpt.exchange_accounts.repository import (
    ExchangeAccountRepository,
)
from app.tradinggpt.exchange_accounts.service import (
    ExchangeAccountService,
)
from app.tradinggpt.scheduler.background_loop import (
    SchedulerBackgroundLoop,
)
from app.tradinggpt.scheduler.distributed_lock import (
    PostgresAdvisorySchedulerLock,
)

from .reconciliation_batch_journal_service import (
    JournaledOrderReconciliationBatchService,
)
from .reconciliation_batch_repository import (
    OrderReconciliationBatchRepository,
)
from .reconciliation_service import (
    AutomaticOrderReconciliationService,
)


def build_exchange_account_service(
    session: Session,
) -> ExchangeAccountService:
    return ExchangeAccountService(
        repository=ExchangeAccountRepository(
            session
        ),
        cipher=CredentialCipher(
            settings
            .exchange_credentials_encryption_key
        ),
    )


def run_order_reconciliation_background_tick(
) -> dict[str, object]:
    if not (
        settings
        .order_reconciliation_background_enabled
    ):
        return {
            "action": "SKIPPED_DISABLED",
            "reason": (
                "Automatic order reconciliation "
                "is disabled."
            ),
        }

    distributed_lock = (
        PostgresAdvisorySchedulerLock(
            engine=engine,
            lock_key=(
                settings
                .order_reconciliation_advisory_lock_key
            ),
        )
    )
    acquired = False

    try:
        acquired = (
            distributed_lock.try_acquire()
        )

        if not acquired:
            return {
                "action": "SKIPPED_LOCKED",
                "reason": (
                    "Another reconciliation "
                    "instance holds the lock."
                ),
            }

        with SessionLocal() as session:
            account_service = (
                build_exchange_account_service(
                    session
                )
            )

            service = (
                AutomaticOrderReconciliationService(
                    session=session,
                    execution_service_factory=(
                        lambda *,
                        account_id,
                        user_id: (
                            account_service
                            .order_execution_service(
                                account_id=(
                                    account_id
                                ),
                                user_id=user_id,
                            )
                        )
                    ),
                    batch_size=(
                        settings
                        .order_reconciliation_batch_size
                    ),
                )
            )

            return (
                JournaledOrderReconciliationBatchService(
                    runner=service,
                    repository=(
                        OrderReconciliationBatchRepository(
                            session
                        )
                    ),
                )
                .run_batch()
            )
    finally:
        if acquired:
            distributed_lock.release()


order_reconciliation_background_loop = (
    SchedulerBackgroundLoop(
        tick_callback=(
            run_order_reconciliation_background_tick
        ),
        poll_interval_seconds=(
            settings
            .order_reconciliation_poll_seconds
        ),
        task_name=(
            "tradinggpt-order-"
            "reconciliation-loop"
        ),
        failure_actions=frozenset(
            {
                "FAILED",
                "PARTIAL",
            }
        ),
    )
)
