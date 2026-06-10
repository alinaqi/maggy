"""Tests for the shared model-routing source of truth."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import model_routing as mr  # noqa: E402


def _which_none(_name):
    return None


def test_detect_uses_env_keys(tmp_path):
    av = mr.detect_available(env={"MINIMAX_API_KEY": "x"}, which=_which_none,
                             ollama=lambda: False, bin_dir=tmp_path)
    assert av["minimax"] is True
    assert av["deepseek"] is False


def test_detect_qwen_requires_ollama(tmp_path):
    # qwen has a cli wrapper but needs ollama up
    av = mr.detect_available(env={}, which=lambda n: "/bin/qwen3" if n == "qwen3" else None,
                             ollama=lambda: False, bin_dir=tmp_path)
    assert av["qwen"] is False
    av2 = mr.detect_available(env={}, which=lambda n: "/bin/qwen3" if n == "qwen3" else None,
                              ollama=lambda: True, bin_dir=tmp_path)
    assert av2["qwen"] is True


def test_recommend_primary_prefers_minimax():
    av = {"minimax": True, "claude": True, "deepseek": True}
    assert mr.recommend_primary(av) == "minimax"


def test_recommend_primary_falls_back_to_claude():
    assert mr.recommend_primary({}) == "claude"


def test_recommend_classifier_prefers_local():
    av = {"qwen": True, "deepseek": True, "minimax": True}
    assert mr.recommend_classifier(av) == "qwen"


def test_classifier_falls_back_to_primary_when_no_cheap():
    av = {"minimax": True}
    assert mr.recommend_classifier(av) == "minimax"


def test_ensure_autocreates_and_persists(tmp_path):
    p = tmp_path / "model-config.json"
    cfg = mr.ensure(p, env={"MINIMAX_API_KEY": "x", "ANTHROPIC_API_KEY": "y"})
    assert cfg["primary"] == "minimax"
    assert cfg["mode"] == "smart"
    assert cfg["auto_detected"] is True
    assert p.exists()
    # second call returns the saved one without re-detecting
    again = mr.ensure(p, env={})
    assert again["primary"] == "minimax"


def test_ensure_respects_existing_primary(tmp_path):
    p = tmp_path / "c.json"
    mr.save({"primary": "deepseek"}, p)
    assert mr.ensure(p, env={"MINIMAX_API_KEY": "x"})["primary"] == "deepseek"


def test_get_primary(tmp_path):
    p = tmp_path / "c.json"
    mr.save({"primary": "kimi"}, p)
    assert mr.get_primary(p) == "kimi"


def test_srooter_id_mapping():
    assert mr.srooter_id("minimax") == "minimax-m2.5"
    assert mr.srooter_id("agy") is None


def test_apply_to_srooter_rewrites_long_context(tmp_path):
    y = tmp_path / "srooter.yaml"
    y.write_text("anthropic_routing:\n  trivial: qwen\n  long_context: claude-max\n")
    ok = mr.apply_to_srooter({"primary": "minimax"}, y)
    assert ok is True
    assert "long_context: minimax-m2.5" in y.read_text()


def test_apply_to_srooter_skips_non_gateway_model(tmp_path):
    y = tmp_path / "srooter.yaml"
    y.write_text("anthropic_routing:\n  long_context: claude-max\n")
    assert mr.apply_to_srooter({"primary": "agy"}, y) is False
