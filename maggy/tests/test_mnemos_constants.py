"""Tests for mnemos constants."""

from maggy.mnemos.constants import (
    CHECKPOINT_THRESHOLD,
    FATIGUE_WEIGHT_TOKEN,
    NODE_TYPES,
    STATE_BOUNDARIES,
    STATE_COMPRESS,
    STATE_EMERGENCY,
    STATE_FLOW,
    STATE_PRE_SLEEP,
    STATE_REM,
    TRANSCRIPT_FULL_BYTES,
)


def test_fatigue_weight_in_range():
    assert 0.0 < FATIGUE_WEIGHT_TOKEN <= 1.0


def test_checkpoint_threshold_above_compress():
    compress_upper = STATE_BOUNDARIES[1][0]
    assert CHECKPOINT_THRESHOLD == compress_upper


def test_state_boundaries_ascending():
    thresholds = [b[0] for b in STATE_BOUNDARIES]
    for i in range(len(thresholds) - 1):
        assert thresholds[i] < thresholds[i + 1]


def test_state_boundaries_cover_all_states():
    states = {b[1] for b in STATE_BOUNDARIES}
    expected = {
        STATE_FLOW, STATE_COMPRESS,
        STATE_PRE_SLEEP, STATE_REM, STATE_EMERGENCY,
    }
    assert states == expected


def test_node_types_is_frozenset():
    assert isinstance(NODE_TYPES, frozenset)
    assert len(NODE_TYPES) == 12


def test_transcript_full_bytes_positive():
    assert TRANSCRIPT_FULL_BYTES > 0
