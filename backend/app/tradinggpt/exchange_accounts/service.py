from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.models.exchange_account import (
    ExchangeAccount,
)
from app.tradinggpt.exchanges.client_factory import (
    create_binance_client_from_credentials,
)
from app.tradinggpt.orders.adapters import (
    BinanceOrderAdapter,
)
from app.tradinggpt.orders.execution_service import (
    OrderExecutionService,
)
from app.tradinggpt.portfolio_sync.binance import (
    BinancePortfolioProvider,
)
from app.tradinggpt.portfolio_sync.models import (
    PortfolioSnapshot,
)

from .crypto import CredentialCipher
from .repository import (
    ExchangeAccountRepository,
)
from .schemas import (
    ExchangeAccountCreateRequest,
    ExchangeAccountStatus,
)


BinanceClientFactory = Callable[..., object]


class ExchangeAccountNotFoundError(
    LookupError
):
    pass


class ExchangeConnectionError(
    RuntimeError
):
    pass


class UnsafeExchangePermissionsError(
    RuntimeError
):
    pass


class ExchangeTradingUnavailableError(
    RuntimeError
):
    pass


class LiveExchangeExecutionDisabledError(
    RuntimeError
):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExchangeAccountService:
    def __init__(
        self,
        *,
        repository: ExchangeAccountRepository,
        cipher: CredentialCipher,
        client_factory: (
            BinanceClientFactory | None
        ) = None,
    ) -> None:
        self.repository = repository
        self.cipher = cipher
        self.client_factory = (
            client_factory
            or create_binance_client_from_credentials
        )

    def list_for_user(
        self,
        user_id: int,
    ) -> list[ExchangeAccount]:
        return self.repository.list_for_user(
            user_id
        )

    def get(
        self,
        *,
        account_id: int,
        user_id: int,
    ) -> ExchangeAccount:
        account = (
            self.repository.get_for_user(
                account_id=account_id,
                user_id=user_id,
            )
        )

        if account is None:
            raise ExchangeAccountNotFoundError(
                "Exchange account was not found."
            )

        return account

    def create_or_replace(
        self,
        *,
        user_id: int,
        request: ExchangeAccountCreateRequest,
    ) -> ExchangeAccount:
        exchange = "BINANCE"
        environment = request.environment.value

        api_key = (
            request.api_key
            .get_secret_value()
            .strip()
        )

        secret_key = (
            request.secret_key
            .get_secret_value()
            .strip()
        )

        account = (
            self.repository.get_by_scope(
                user_id=user_id,
                exchange=exchange,
                environment=environment,
            )
        )

        encrypted_api_key = (
            self.cipher.encrypt(api_key)
        )

        encrypted_secret_key = (
            self.cipher.encrypt(secret_key)
        )

        if account is None:
            account = ExchangeAccount(
                user_id=user_id,
                exchange=exchange,
                environment=environment,
                label=request.label,
                encrypted_api_key=(
                    encrypted_api_key
                ),
                encrypted_secret_key=(
                    encrypted_secret_key
                ),
                api_key_hint=self._key_hint(
                    api_key
                ),
                status=(
                    ExchangeAccountStatus
                    .UNVERIFIED
                    .value
                ),
            )

            self.repository.add(account)
        else:
            account.label = request.label
            account.encrypted_api_key = (
                encrypted_api_key
            )
            account.encrypted_secret_key = (
                encrypted_secret_key
            )
            account.api_key_hint = (
                self._key_hint(api_key)
            )
            account.status = (
                ExchangeAccountStatus
                .UNVERIFIED
                .value
            )
            account.can_trade = None
            account.can_deposit = None
            account.can_withdraw = None
            account.last_checked_at = None
            account.last_error = None
            account.updated_at = utc_now()

        return self.repository.save(
            account
        )

    def verify(
        self,
        *,
        account_id: int,
        user_id: int,
    ) -> ExchangeAccount:
        account = self.get(
            account_id=account_id,
            user_id=user_id,
        )

        client = self._build_client(
            account
        )

        return self._verify_client(
            account=account,
            client=client,
        )

    def portfolio(
        self,
        *,
        account_id: int,
        user_id: int,
    ) -> PortfolioSnapshot:
        account = self.get(
            account_id=account_id,
            user_id=user_id,
        )

        client = self._build_client(
            account
        )

        self._verify_client(
            account=account,
            client=client,
        )

        try:
            snapshot = (
                BinancePortfolioProvider(
                    client=client
                ).get_snapshot()
            )
        except Exception as exc:
            self._mark_connection_error(
                account
            )

            raise ExchangeConnectionError(
                "Failed to synchronize "
                "Binance portfolio."
            ) from exc

        return snapshot

    def order_execution_service(
        self,
        *,
        account_id: int,
        user_id: int,
    ) -> OrderExecutionService:
        account = self.get(
            account_id=account_id,
            user_id=user_id,
        )

        if account.environment != "TESTNET":
            raise (
                LiveExchangeExecutionDisabledError(
                    "LIVE exchange execution "
                    "is disabled."
                )
            )

        client = self._build_client(
            account
        )

        self._verify_client(
            account=account,
            client=client,
        )

        if account.can_trade is not True:
            raise ExchangeTradingUnavailableError(
                "Binance account does not "
                "permit trading."
            )

        return OrderExecutionService(
            adapters=[
                BinanceOrderAdapter(
                    client=client,
                    testnet=True,
                ),
            ]
        )

    def delete(
        self,
        *,
        account_id: int,
        user_id: int,
    ) -> None:
        account = self.get(
            account_id=account_id,
            user_id=user_id,
        )

        self.repository.delete(account)

    def _build_client(
        self,
        account: ExchangeAccount,
    ) -> object:
        api_key = self.cipher.decrypt(
            account.encrypted_api_key
        )

        secret_key = self.cipher.decrypt(
            account.encrypted_secret_key
        )

        return self.client_factory(
            api_key=api_key,
            secret_key=secret_key,
            testnet=(
                account.environment
                == "TESTNET"
            ),
        )

    def _verify_client(
        self,
        *,
        account: ExchangeAccount,
        client: object,
    ) -> ExchangeAccount:
        get_account = getattr(
            client,
            "get_account",
            None,
        )

        if not callable(get_account):
            self._mark_connection_error(
                account
            )

            raise ExchangeConnectionError(
                "Binance client does not "
                "support account verification."
            )

        try:
            payload = get_account()
        except Exception as exc:
            self._mark_connection_error(
                account
            )

            raise ExchangeConnectionError(
                "Binance rejected the "
                "credentials or connection failed."
            ) from exc

        if not isinstance(payload, dict):
            self._mark_connection_error(
                account
            )

            raise ExchangeConnectionError(
                "Binance returned an invalid "
                "account response."
            )

        account.can_trade = self._permission(
            payload,
            "canTrade",
        )

        account.can_deposit = self._permission(
            payload,
            "canDeposit",
        )

        account.can_withdraw = self._permission(
            payload,
            "canWithdraw",
        )

        account.last_checked_at = utc_now()
        account.updated_at = utc_now()

        if account.can_withdraw:
            account.status = (
                ExchangeAccountStatus
                .UNSAFE
                .value
            )
            account.last_error = (
                "Withdrawal permission "
                "must be disabled."
            )

            self.repository.save(account)

            raise (
                UnsafeExchangePermissionsError(
                    "Binance API key has "
                    "withdrawal permission enabled."
                )
            )

        account.status = (
            ExchangeAccountStatus
            .CONNECTED
            .value
        )
        account.last_error = None

        return self.repository.save(
            account
        )

    def _mark_connection_error(
        self,
        account: ExchangeAccount,
    ) -> None:
        account.status = (
            ExchangeAccountStatus
            .ERROR
            .value
        )
        account.last_checked_at = utc_now()
        account.updated_at = utc_now()
        account.last_error = (
            "Binance connection failed."
        )

        self.repository.save(account)

    @staticmethod
    def _permission(
        payload: dict[str, Any],
        name: str,
    ) -> bool:
        return payload.get(name) is True

    @staticmethod
    def _key_hint(
        api_key: str,
    ) -> str:
        if len(api_key) <= 8:
            return "••••••••"

        return (
            f"{api_key[:4]}"
            "••••"
            f"{api_key[-4:]}"
        )
