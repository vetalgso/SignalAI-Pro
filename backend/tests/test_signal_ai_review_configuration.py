from importlib.util import (
    module_from_spec,
    spec_from_file_location,
)
from pathlib import Path

from app.core.config import Settings


def load_ai_status():
    path = Path("app/api/ai.py")
    spec = spec_from_file_location(
        "signal_ai_status_module",
        path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Unable to load AI status module"
        )

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ai_status


ai_status = load_ai_status()


def test_ai_review_is_disabled_by_default() -> None:
    settings = Settings(_env_file=None)

    assert settings.signal_ai_review_enabled is False
    assert settings.signal_ai_provider == "openai"
    assert settings.signal_ai_model == "gpt-5-mini"
    assert settings.signal_ai_max_candidates == 3


def test_ai_review_policy_is_bounded() -> None:
    settings = Settings(_env_file=None)

    assert settings.signal_ai_min_confidence == 60
    assert settings.signal_ai_min_ranking_score == 65
    assert settings.signal_ai_min_consensus_score == 90
    assert settings.signal_ai_min_timeframe_score == 90
    assert settings.signal_ai_max_quality_penalty == 10


def test_ai_status_never_returns_api_key() -> None:
    payload = ai_status()
    serialized = str(payload).lower()

    assert "api_key" not in serialized
    assert "sk-" not in serialized
    assert "review_policy" in payload


def test_ai_threshold_validation() -> None:
    settings = Settings(
        _env_file=None,
        signal_ai_max_candidates=10,
        signal_ai_min_confidence=100,
        signal_ai_min_ranking_score=100,
        signal_ai_min_consensus_score=100,
        signal_ai_min_timeframe_score=100,
        signal_ai_max_quality_penalty=0,
    )

    assert settings.signal_ai_max_candidates == 10
    assert settings.signal_ai_max_quality_penalty == 0
