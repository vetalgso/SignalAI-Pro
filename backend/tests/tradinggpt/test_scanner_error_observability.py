import asyncio
import re

import pytest

from app.tradinggpt.modules.market_scanner import (
    CryptoMarketScanner,
)


def run_failure(
    error: Exception,
) -> dict[str, str]:
    scanner = CryptoMarketScanner(
        crypto_asset_module=object(),
    )

    async def fail(
        *,
        asset: str,
        risk_level: str,
    ):
        del asset, risk_level
        raise error

    scanner._analyze_asset = fail

    result = asyncio.run(
        scanner.scan(
            assets=["MARSCOIN"],
            risk_level="medium",
            limit=1,
        )
    )

    assert result["scanned_assets"] == 1
    assert result["successful_assets"] == 0
    assert result["failed_assets"] == 1
    assert result["candidates"] == []

    errors = result["errors"]
    assert len(errors) == 1

    return errors[0]


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (
            TypeError(
                "float() argument must not be None"
            ),
            "INVALID_ANALYSIS_PAYLOAD",
        ),
        (
            ValueError("invalid numeric value"),
            "INVALID_ANALYSIS_PAYLOAD",
        ),
        (
            TimeoutError("provider timed out"),
            "UPSTREAM_TIMEOUT",
        ),
        (
            ConnectionError("provider unavailable"),
            "UPSTREAM_CONNECTION_ERROR",
        ),
        (
            RuntimeError("unexpected failure"),
            "UNEXPECTED_ANALYSIS_ERROR",
        ),
    ],
)
def test_scanner_records_safe_error_metadata(
    error,
    expected_code,
) -> None:
    payload = run_failure(error)

    assert payload["asset"] == "MARSCOIN"
    assert payload["error"] == type(error).__name__
    assert payload["error_code"] == expected_code
    assert payload["stage"] == "ASSET_ANALYSIS"
    assert re.fullmatch(
        (
            r"test_scanner_error_observability"
            r"\.py:fail:\d+"
        ),
        payload["location"],
    )


def test_scanner_error_metadata_omits_message() -> None:
    secret = "secret-value-that-must-not-leak"
    payload = run_failure(
        RuntimeError(secret)
    )
    serialized = str(payload)

    assert secret not in serialized
    assert "message" not in payload
    assert "args" not in payload
    assert "traceback" not in payload
