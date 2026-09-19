"""Tests for the shared model-routing source of truth."""

from pathlib import Path
import json
import os
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


def test_srooter_id_switchable_backends():
    # The four backends Claude Code can be switched to map to real srooter aliases.
    assert mr.srooter_id("deepseek") == "deepseek-pro"
    assert mr.srooter_id("kimi") == "kimi-k3"
    assert mr.srooter_id("glm") == "glm-5.3"
    assert mr.srooter_id("codex") == "codex"


def test_apply_to_srooter_rewrites_long_context(tmp_path):
    y = tmp_path / "srooter.yaml"
    y.write_text("anthropic_routing:\n  trivial: qwen\n  long_context: claude-max\n")
    ok = mr.apply_to_srooter({"primary": "minimax"}, y)
    assert ok is True
    assert "long_context: minimax-m2.5" in y.read_text()


def test_apply_to_srooter_rewrites_both_coding_routes(tmp_path):
    # Switching must move both real-coding routes, not just long_context, so
    # substantive traffic follows the chosen backend too.
    y = tmp_path / "srooter.yaml"
    y.write_text(
        "anthropic_routing:\n"
        "  trivial: gemini\n"
        "  long_context: claude-max\n"
        "  substantive: claude-max\n"
        "  think: deepseek-pro\n"
    )
    ok = mr.apply_to_srooter({"primary": "deepseek"}, y)
    assert ok is True
    out = y.read_text()
    assert "long_context: deepseek-pro" in out
    assert "substantive: deepseek-pro" in out
    # trivial stays fast/cheap; think is left untouched
    assert "trivial: gemini" in out


def test_apply_to_srooter_skips_non_gateway_model(tmp_path):
    y = tmp_path / "srooter.yaml"
    y.write_text("anthropic_routing:\n  long_context: claude-max\n")
    assert mr.apply_to_srooter({"primary": "agy"}, y) is False


def test_direct_config_for_anthropic_compatible_providers():
    for logical, host in (("deepseek", "api.deepseek.com"),
                          ("glm", "api.z.ai"),
                          ("kimi", "api.moonshot.ai")):
        d = mr.direct_config(logical)
        assert d is not None
        assert host in d["base_url"] and d["base_url"].endswith("/anthropic")
        assert d["model"] and d["token_envs"]


def test_direct_config_none_without_anthropic_endpoint():
    # codex (OpenAI) has no Anthropic Messages API; claude/minimax aren't direct here.
    assert mr.direct_config("codex") is None
    assert mr.direct_config("minimax") is None
    assert mr.direct_config("unknown") is None


def test_write_launcher_creates_executable(tmp_path):
    path = mr.write_launcher("deepseek", bin_dir=tmp_path)
    assert path is not None and path.name == "claude-deepseek"
    assert os.access(path, os.X_OK)
    body = path.read_text()
    assert "https://api.deepseek.com/anthropic" in body
    assert 'ANTHROPIC_MODEL="deepseek-v4-pro"' in body
    assert 'ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"' in body
    assert "DEEPSEEK_API_KEY" in body
    assert body.startswith("#!/usr/bin/env bash")
    assert "exec claude" in body


def test_write_launcher_rejects_non_direct(tmp_path):
    assert mr.write_launcher("codex", bin_dir=tmp_path) is None
    assert not (tmp_path / "claude-codex").exists()


def _write_auth(tmp_path, data):
    p = tmp_path / "auth.json"
    p.write_text(json.dumps(data))
    return p


def test_codex_auth_detects_subscription(tmp_path):
    p = _write_auth(tmp_path, {"auth_mode": "chatgpt",
                               "tokens": {"access_token": "x"}})
    a = mr.codex_auth(env={}, auth_path=p)
    assert a == {"api_key": False, "subscription": True}


def test_codex_auth_detects_real_api_key(tmp_path):
    a = mr.codex_auth(env={"OPENAI_API_KEY": "sk-abc123"},
                      auth_path=tmp_path / "missing.json")
    assert a["api_key"] is True and a["subscription"] is False


def test_codex_auth_ignores_srooter_dev_key(tmp_path):
    # a srt_ srooter dev key is not a real OpenAI key
    a = mr.codex_auth(env={"OPENAI_API_KEY": "srt_devkey"},
                      auth_path=tmp_path / "missing.json")
    assert a["api_key"] is False and a["subscription"] is False


def test_codex_mode_prefers_api_key_then_subscription(tmp_path):
    sub = _write_auth(tmp_path, {"auth_mode": "chatgpt",
                                 "tokens": {"access_token": "x"}})
    # both available -> api_key wins (can back a Claude Code model)
    both = mr.codex_mode({}, env={"OPENAI_API_KEY": "sk-x"}, auth_path=sub)
    assert both == "api_key"
    # only subscription -> subscription
    only_sub = mr.codex_mode({}, env={}, auth_path=sub)
    assert only_sub == "subscription"
    # nothing -> none
    assert mr.codex_mode({}, env={}, auth_path=tmp_path / "none.json") == "none"


def test_codex_mode_explicit_pref_wins_when_available(tmp_path):
    sub = _write_auth(tmp_path, {"auth_mode": "chatgpt",
                                 "tokens": {"access_token": "x"}})
    cfg = {"codex_auth": "subscription"}
    # even with an api key present, an explicit subscription pref is honored
    assert mr.codex_mode(cfg, env={"OPENAI_API_KEY": "sk-x"}, auth_path=sub) == "subscription"
    # but an explicit pref that isn't available falls back to none
    assert mr.codex_mode({"codex_auth": "api_key"}, env={}, auth_path=sub) == "none"
