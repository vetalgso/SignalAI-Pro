from __future__ import annotations

from cryptography.fernet import (
    Fernet,
    InvalidToken,
)


class CredentialEncryptionError(
    RuntimeError
):
    pass


class CredentialCipher:
    def __init__(
        self,
        key: str,
    ) -> None:
        normalized = key.strip()

        if not normalized:
            raise CredentialEncryptionError(
                "Exchange credential encryption "
                "is not configured."
            )

        try:
            self._fernet = Fernet(
                normalized.encode("ascii")
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise CredentialEncryptionError(
                "Exchange credential encryption "
                "key is invalid."
            ) from exc

    def encrypt(
        self,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise CredentialEncryptionError(
                "Credential must not be empty."
            )

        return self._fernet.encrypt(
            normalized.encode("utf-8")
        ).decode("ascii")

    def decrypt(
        self,
        token: str,
    ) -> str:
        try:
            return self._fernet.decrypt(
                token.encode("ascii")
            ).decode("utf-8")
        except (
            InvalidToken,
            UnicodeError,
            ValueError,
        ) as exc:
            raise CredentialEncryptionError(
                "Stored exchange credentials "
                "cannot be decrypted."
            ) from exc
