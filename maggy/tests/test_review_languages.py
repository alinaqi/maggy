"""Tests for the extensible language registry + token resolution (no heavy deps)."""

from __future__ import annotations

import pytest

from maggy.review import config as review_config
from maggy.review import languages as lang


@pytest.fixture(autouse=True)
def _restore_registry():
    """Snapshot/restore REGISTRY so register tests don't leak."""
    saved = dict(lang.REGISTRY)
    yield
    lang.REGISTRY.clear()
    lang.REGISTRY.update(saved)


class TestDetect:
    def test_detects_by_extension(self):
        files = ["app/main.py", "web/x.tsx", "svc/h.go", "lib/a.rs"]
        assert lang.detect_languages(files) == ["go", "python", "rust", "typescript"]

    def test_db_by_path_marker(self):
        assert "db" in lang.detect_languages(["migrations/0001_init.py"])
        assert "db" in lang.detect_languages(["db/schema.sql"])

    def test_seeded_common_set_present(self):
        for name in ("go", "rust", "java", "csharp", "ruby", "php"):
            assert name in lang.supported()

    def test_unknown_extension_ignored(self):
        assert lang.detect_languages(["README.md", "logo.png"]) == []


class TestSkillLoading:
    def test_base_always_loads(self):
        out = lang.load_skill([])
        assert "review skill" in out.lower() or len(out) > 0

    def test_per_language_skill_appended(self):
        out = lang.load_skill(["go"])
        assert "Go" in out

    def test_unknown_language_skipped_not_crash(self):
        out = lang.load_skill(["klingon"])  # no skill file -> just base
        assert isinstance(out, str)


class TestExtensibility:
    def test_register_language(self):
        lang.register_language(lang.Language("kotlin", (".kt", ".kts")))
        assert "kotlin" in lang.supported()
        assert "kotlin" in lang.detect_languages(["app/Main.kt"])

    def test_load_from_config(self):
        added = lang.load_from_config([{"name": "scala", "extensions": [".scala"]}])
        assert added == ["scala"]
        assert "scala" in lang.detect_languages(["x.scala"])

    def test_load_from_config_skips_malformed(self):
        added = lang.load_from_config([{"no_name": True}, {"name": "elixir", "extensions": [".ex"]}])
        assert added == ["elixir"]


class TestTokenResolution:
    def test_override_wins(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "env_tok")
        assert review_config.resolve_token("override", "config_tok") == "override"

    def test_config_beats_env(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "env_tok")
        assert review_config.resolve_token(None, "config_tok") == "config_tok"

    def test_env_fallback(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "env_tok")
        assert review_config.resolve_token(None, "") == "env_tok"

    def test_none_when_nothing(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        assert review_config.resolve_token(None, "") is None

    def test_whitespace_ignored(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        assert review_config.resolve_token("   ", "  ") is None
