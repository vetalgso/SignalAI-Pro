import pytest

from app.tradinggpt.scoring.engine import ScoringEngine


def forecast(*items):
    return {
        "forecasts": [
            {
                "horizon_minutes": horizon,
                "probabilities": {
                    "up": up,
                    "down": down,
                },
            }
            for horizon, up, down in items
        ],
    }


def consensus(
    payload,
    trade_direction="LONG",
):
    return ScoringEngine.timeframe_analysis(
        payload,
        trade_direction=trade_direction,
    )["timeframe_consensus_score"]


def test_all_timeframes_matching_trade_score_100():
    result = consensus(
        forecast(
            (60, 0.8, 0.1),
            (240, 0.8, 0.1),
            (1440, 0.8, 0.1),
        ),
        trade_direction="LONG",
    )

    assert result == 100.0


def test_all_timeframes_opposing_trade_score_zero():
    result = consensus(
        forecast(
            (60, 0.1, 0.8),
            (240, 0.1, 0.8),
            (1440, 0.1, 0.8),
        ),
        trade_direction="LONG",
    )

    assert result == 0.0


def test_all_neutral_timeframes_score_50():
    result = consensus(
        forecast(
            (60, 0.5, 0.5),
            (240, 0.5, 0.5),
            (1440, 0.5, 0.5),
        ),
        trade_direction="LONG",
    )

    assert result == 50.0


def test_neutral_horizon_dilutes_matching_direction():
    result = consensus(
        forecast(
            (60, 0.8, 0.1),
            (240, 0.5, 0.5),
            (1440, 0.5, 0.5),
        ),
        trade_direction="LONG",
    )

    assert 50.0 < result < 100.0


def test_neutral_horizon_dilutes_opposing_direction():
    result = consensus(
        forecast(
            (60, 0.1, 0.8),
            (240, 0.5, 0.5),
            (1440, 0.5, 0.5),
        ),
        trade_direction="LONG",
    )

    assert 0.0 < result < 50.0


@pytest.mark.parametrize(
    ("trade_direction", "up", "down"),
    [
        ("LONG", 0.8, 0.1),
        ("SHORT", 0.1, 0.8),
    ],
)
def test_alignment_uses_candidate_direction(
    trade_direction,
    up,
    down,
):
    matching = consensus(
        forecast((1440, up, down)),
        trade_direction=trade_direction,
    )
    opposing = consensus(
        forecast((1440, down, up)),
        trade_direction=trade_direction,
    )

    assert matching == 100.0
    assert opposing == 0.0


def test_neutral_trade_uses_dominant_direction():
    result = consensus(
        forecast(
            (60, 0.8, 0.1),
            (240, 0.5, 0.5),
        ),
        trade_direction="NEUTRAL",
    )

    assert 50.0 < result < 100.0
