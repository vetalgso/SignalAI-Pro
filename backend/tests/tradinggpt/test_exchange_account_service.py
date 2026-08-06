from __future__ import annotations

from datetime import datetime, timezone

import pytest
from cryptography.fernet import Fernet

from app.models.exchange_account import (
    ExchangeAccount,
)
from app.tradinggpt.exchange_accounts.crypto import (
    CredentialCipher,
)
from app.tradinggpt.exchange_accounts.schemas import (
    ExchangeAccountCreateRequest,
    ExchangeAccountResponse,
)
from app.tradinggpt.exchange_accounts.service import (
    ExchangeAccountNotFoundError,
    ExchangeAccountService,
    ExchangeTradingUnavailableError,
    LiveExchangeExecutionDisabledError,
    UnsafeExchangePermissionsError,
)


class FakeRepository:
    def __init__(self) -> None:
        self.account: (
            ExchangeAccount | None
        ) = None

    def list_for_user(
        self,
        user_id: int,
    ) -> list[ExchangeAccount]:
        if (
            self.account is not None
            and self.account.user_id
            == user_id
        ):
            return [self.account]

        return []

    def get_for_user(
        self,
        *,
        account_id: int,
        user_id: int,
    ) -> ExchangeAccount | None:
        if (
            self.account is not None
            and self.account.id
            == account_id
            and self.account.user_id
            == user_id
        ):
            return self.account

        return None

    def get_by_scope(
        self,
        *,
        user_id: int,
        exchange: str,
        environment: str,
    ) -> ExchangeAccount | None:
        account = self.account

        if account is None:
            return None

        if (
            account.user_id == user_id
            and account.exchange == exchange
            and account.environment
            == environment
        ):
            return account

        return None

    def add(
        self,
        account: ExchangeAccount,
    ) -> ExchangeAccount:
        account.id = 1

        now = datetime.now(
            timezone.utc
        )

        account.created_at = now
        account.updated_at = now
        self.account = account

        return account

    def save(
        self,
        account: ExchangeAccount,
    ) -> ExchangeAccount:
        if account.id is None:
            account.id = 1

        now = datetime.now(
            timezone.utc
        )

        if account.created_at is None:
            account.created_at = now

        account.updated_at = now
        self.account = account

        return account

    def delete(
        self,
        account: ExchangeAccount,
    ) -> None:
        if self.account is account:
            self.account = None


class FakeBinanceClient:
    def __init__(
        self,
        *,
        can_withdraw: bool = False,
        can_trade: bool = True,
    ) -> None:
        self.can_withdraw = (
            can_withdraw
        )
        self.can_trade = (
            can_trade
        )

    def get_account(
        self,
    ) -> dict[str, object]:
        return {
            "canTrade": self.can_trade,
            "canDeposit": True,
            "canWithdraw": (
                self.can_withdraw
            ),
            "balances": [
                {
                    "asset": "BTC",
                    "free": "0.5",
                    "locked": "0.1",
                },
                {
                    "asset": "USDT",
                    "free": "1000",
                    "locked": "0",
                },
            ],
        }

    def get_open_orders(
        self,
    ) -> list[dict[str, object]]:
        return [
            {
                "orderId": 42,
                "clientOrderId": "test",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "type": "LIMIT",
                "status": "NEW",
                "price": "60000",
                "origQty": "0.01",
                "executedQty": "0",
            },
        ]


def request(
    *,
    environment: str = "TESTNET",
) -> ExchangeAccountCreateRequest:
    return ExchangeAccountCreateRequest(
        label="My Binance",
        environment=environment,
        api_key="api-key-12345678",
        secret_key="secret-key-12345678",
    )


def build_service(
    *,
    client: FakeBinanceClient
    | None = None,
) -> tuple[
    ExchangeAccountService,
    FakeRepository,
]:
    repository = FakeRepository()

    cipher = CredentialCipher(
        Fernet.generate_key().decode(
            "ascii"
        )
    )

    selected_client = (
        client or FakeBinanceClient()
    )

    service = ExchangeAccountService(
        repository=repository,
        cipher=cipher,
        client_factory=lambda **_: (
            selected_client
        ),
    )

    return service, repository


def test_cipher_encrypts_credentials(
) -> None:
    cipher = CredentialCipher(
        Fernet.generate_key().decode(
            "ascii"
        )
    )

    plaintext = "sensitive-secret"
    encrypted = cipher.encrypt(
        plaintext
    )

    assert encrypted != plaintext
    assert plaintext not in encrypted
    assert (
        cipher.decrypt(encrypted)
        == plaintext
    )


def test_account_credentials_are_not_exposed(
) -> None:
    service, repository = (
        build_service()
    )

    account = service.create_or_replace(
        user_id=7,
        request=request(),
    )

    assert repository.account is account

    assert (
        account.encrypted_api_key
        != "api-key-12345678"
    )

    assert (
        account.encrypted_secret_key
        != "secret-key-12345678"
    )

    payload = (
        ExchangeAccountResponse
        .model_validate(account)
        .model_dump(mode="json")
    )

    assert "encrypted_api_key" not in payload
    assert "encrypted_secret_key" not in payload
    assert "api_key" not in payload
    assert "secret_key" not in payload
    assert payload["api_key_hint"] == (
        "api-••••5678"
    )


def test_verify_marks_account_connected(
) -> None:
    service, _ = build_service()

    account = service.create_or_replace(
        user_id=7,
        request=request(),
    )

    verified = service.verify(
        account_id=account.id,
        user_id=7,
    )

    assert verified.status == "CONNECTED"
    assert verified.can_trade is True
    assert verified.can_deposit is True
    assert verified.can_withdraw is False
    assert (
        verified.last_checked_at
        is not None
    )


def test_withdrawal_permission_is_rejected(
) -> None:
    service, _ = build_service(
        client=FakeBinanceClient(
            can_withdraw=True
        )
    )

    account = service.create_or_replace(
        user_id=7,
        request=request(),
    )

    with pytest.raises(
        UnsafeExchangePermissionsError
    ):
        service.verify(
            account_id=account.id,
            user_id=7,
        )

    assert account.status == "UNSAFE"
    assert account.can_withdraw is True


def test_portfolio_uses_existing_provider(
) -> None:
    service, _ = build_service()

    account = service.create_or_replace(
        user_id=7,
        request=request(),
    )

    snapshot = service.portfolio(
        account_id=account.id,
        user_id=7,
    )

    assert snapshot.source == "BINANCE"
    assert len(snapshot.balances) == 2
    assert len(snapshot.open_orders) == 1
    assert len(snapshot.positions) == 2


def test_order_execution_uses_owned_testnet_account(
) -> None:
    service, _ = build_service()

    account = service.create_or_replace(
        user_id=7,
        request=request(),
    )

    execution = (
        service.order_execution_service(
            account_id=account.id,
            user_id=7,
        )
    )

    assert execution.supports(
        "BINANCE"
    ) is True

    assert execution.supports(
        "PAPER"
    ) is False


def test_order_execution_rejects_foreign_account(
) -> None:
    service, _ = build_service()

    account = service.create_or_replace(
        user_id=7,
        request=request(),
    )

    with pytest.raises(
        ExchangeAccountNotFoundError
    ):
        service.order_execution_service(
            account_id=account.id,
            user_id=8,
        )


def test_order_execution_rejects_live_account(
) -> None:
    service, _ = build_service()

    account = service.create_or_replace(
        user_id=7,
        request=request(
            environment="LIVE"
        ),
    )

    with pytest.raises(
        LiveExchangeExecutionDisabledError
    ):
        service.order_execution_service(
            account_id=account.id,
            user_id=7,
        )


def test_order_execution_requires_trade_permission(
) -> None:
    service, _ = build_service(
        client=FakeBinanceClient(
            can_trade=False
        )
    )

    account = service.create_or_replace(
        user_id=7,
        request=request(),
    )

    with pytest.raises(
        ExchangeTradingUnavailableError
    ):
        service.order_execution_service(
            account_id=account.id,
            user_id=7,
        )
