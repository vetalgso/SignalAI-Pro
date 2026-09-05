import pytest

from app.tradinggpt.modules.crypto_asset import (
    CryptoAssetAnalysisModule,
)
from app.tradinggpt.quality_guard import (
    AnalysisQualityGuard,
)


@pytest.mark.parametrize(
    "signal",
    [
        {
            "indicators": {
                "volume": {
                    "ratio": None,
                },
            },
        },
        {
            "indicators": {
                "volume": {},
            },
        },
        {
            "indicators": {
                "volume": None,
            },
        },
        {
            "indicators": {},
        },
        {
            "indicators": None,
        },
        {
            "indicators": {
                "volume": {
                    "ratio": "invalid",
                },
            },
        },
        {
            "indicators": {
                "volume": {
                    "ratio": float("nan"),
                },
            },
        },
    ],
)
def test_missing_or_invalid_volume_ratio_is_penalized(
    signal,
) -> None:
    assert (
        AnalysisQualityGuard.volume_penalty(signal)
        == 10
    )


@pytest.mark.parametrize(
    ("ratio", "expected"),
    [
        (0.24, 15),
        (0.25, 10),
        (0.50, 5),
        (0.80, 0),
        ("1.25", 0),
    ],
)
def test_valid_volume_ratio_preserves_thresholds(
    ratio,
    expected,
) -> None:
    signal = {
        "indicators": {
            "volume": {
                "ratio": ratio,
            },
        },
    }

    assert (
        AnalysisQualityGuard.volume_penalty(signal)
        == expected
    )

@pytest.mark.parametrize(
    "ratio",
    [
        None,
        "invalid",
        float("nan"),
    ],
)
def test_invalid_volume_ratio_is_high_risk(
    ratio,
) -> None:
    signal = {
        "decision": {
            "warnings": [],
        },
        "indicators": {
            "volume": {
                "ratio": ratio,
            },
        },
    }

    assert (
        CryptoAssetAnalysisModule._risk_level(
            signal,
            forecast=None,
            profile_risk="medium",
        )
        == "high"
    )


@pytest.mark.parametrize(
    "signal",
    [
        {
            "decision": {
                "warnings": [],
            },
            "indicators": {},
        },
        {
            "decision": {
                "warnings": [],
            },
            "indicators": None,
        },
        {
            "decision": None,
            "indicators": {
                "volume": None,
            },
        },
    ],
)
def test_missing_volume_payload_is_high_risk(
    signal,
) -> None:
    assert (
        CryptoAssetAnalysisModule._risk_level(
            signal,
            forecast=None,
            profile_risk="low",
        )
        == "high"
    )


def test_valid_volume_ratio_preserves_profile_risk() -> None:
    signal = {
        "decision": {
            "warnings": [],
        },
        "indicators": {
            "volume": {
                "ratio": 1.0,
            },
        },
    }

    assert (
        CryptoAssetAnalysisModule._risk_level(
            signal,
            forecast=None,
            profile_risk="medium",
        )
        == "medium"
    )

