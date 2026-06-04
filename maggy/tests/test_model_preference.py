"""Tests for Maggy reading the shared followed-model preference."""

from __future__ import annotations

import json

from maggy.process.model_preference import followed_model


def _write(tmp_path, primary):
    p = tmp_path / "model-config.json"
    p.write_text(json.dumps({"primary": primary}))
    return p


def test_maps_logical_to_maggy_name(tmp_path):
    p = _write(tmp_path, "deepseek")
    assert followed_model(p, known={"deepseek-pro"}) == "deepseek-pro"


def test_minimax_passthrough(tmp_path):
    p = _write(tmp_path, "minimax")
    assert followed_model(p, known={"minimax"}) == "minimax"


def test_unknown_model_returns_none(tmp_path):
    p = _write(tmp_path, "minimax")
    assert followed_model(p, known={"claude"}) is None


def test_missing_config_returns_none(tmp_path):
    assert followed_model(tmp_path / "nope.json", known={"minimax"}) is None


def test_blank_primary_returns_none(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"primary": ""}))
    assert followed_model(p, known={"minimax"}) is None


def test_defaults_known_to_pi_registry(tmp_path):
    # known=None should validate against the real DEFAULT_MODELS (minimax added)
    p = _write(tmp_path, "minimax")
    assert followed_model(p) == "minimax"
