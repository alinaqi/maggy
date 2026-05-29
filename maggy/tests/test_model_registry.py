"""Tests for user model registry — add, validate, remove custom AI models."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def cfg_path(tmp_path: Path) -> Path:
    return tmp_path / "council.yaml"


class TestAddModel:
    def test_adds_cli_model(self, cfg_path):
        from maggy.services.model_registry import add_model
        result = add_model(
            model_id="my-llama",
            label="Local Llama",
            access_type="cli",
            cli_cmd="ollama run llama3",
            cfg_path=cfg_path,
        )
        assert result["ok"]
        assert result["model"]["id"] == "my-llama"

    def test_adds_api_model(self, cfg_path):
        from maggy.services.model_registry import add_model
        result = add_model(
            model_id="custom-gpt",
            label="Custom GPT",
            access_type="api",
            api_key="sk-test-123",
            api_base="https://api.openai.com/v1",
            cfg_path=cfg_path,
        )
        assert result["ok"]
        assert result["model"]["id"] == "custom-gpt"

    def test_rejects_duplicate(self, cfg_path):
        from maggy.services.model_registry import add_model
        add_model(
            model_id="dupe", label="D",
            access_type="cli", cli_cmd="echo hi",
            cfg_path=cfg_path,
        )
        result = add_model(
            model_id="dupe", label="D2",
            access_type="cli", cli_cmd="echo hi2",
            cfg_path=cfg_path,
        )
        assert not result["ok"]
        assert "exists" in result["error"].lower()

    def test_rejects_missing_cmd(self, cfg_path):
        from maggy.services.model_registry import add_model
        result = add_model(
            model_id="bad", label="Bad",
            access_type="cli", cli_cmd="",
            cfg_path=cfg_path,
        )
        assert not result["ok"]

    def test_persists_to_config(self, cfg_path):
        from maggy.services.council_config import load_council_config
        from maggy.services.model_registry import add_model
        add_model(
            model_id="persisted", label="Persisted",
            access_type="cli", cli_cmd="echo test",
            cfg_path=cfg_path,
        )
        cfg = load_council_config(cfg_path)
        found = cfg.get_model("persisted")
        assert found is not None
        assert found.label == "Persisted"


class TestRemoveModel:
    def test_removes_custom_model(self, cfg_path):
        from maggy.services.model_registry import add_model, remove_model
        add_model(
            model_id="temp", label="Temp",
            access_type="cli", cli_cmd="echo test",
            cfg_path=cfg_path,
        )
        result = remove_model("temp", cfg_path=cfg_path)
        assert result["ok"]

    def test_rejects_unknown(self, cfg_path):
        from maggy.services.model_registry import remove_model
        result = remove_model("nonexistent", cfg_path=cfg_path)
        assert not result["ok"]

    def test_rejects_builtin(self, cfg_path):
        from maggy.services.model_registry import remove_model
        result = remove_model("claude-sonnet", cfg_path=cfg_path)
        assert not result["ok"]
        assert "built-in" in result["error"].lower()


class TestValidateModel:
    def test_validates_cli_exists(self, cfg_path):
        from maggy.services.model_registry import validate_model
        result = validate_model(access_type="cli", cli_cmd="echo hello")
        assert result["valid"]

    def test_rejects_missing_cli(self, cfg_path):
        from maggy.services.model_registry import validate_model
        result = validate_model(
            access_type="cli",
            cli_cmd="/nonexistent/binary arg",
        )
        assert not result["valid"]

    def test_validates_api_key_format(self, cfg_path):
        from maggy.services.model_registry import validate_model
        result = validate_model(
            access_type="api", api_key="sk-test-abc123",
        )
        assert result["valid"]

    def test_rejects_empty_api_key(self, cfg_path):
        from maggy.services.model_registry import validate_model
        result = validate_model(access_type="api", api_key="")
        assert not result["valid"]


class TestListModels:
    def test_includes_custom(self, cfg_path):
        from maggy.services.model_registry import add_model, list_models
        add_model(
            model_id="custom-1", label="Custom",
            access_type="cli", cli_cmd="echo hi",
            cfg_path=cfg_path,
        )
        models = list_models(cfg_path=cfg_path)
        ids = [m["id"] for m in models]
        assert "custom-1" in ids

    def test_marks_custom_flag(self, cfg_path):
        from maggy.services.model_registry import add_model, list_models
        add_model(
            model_id="user-added", label="User",
            access_type="cli", cli_cmd="echo hi",
            cfg_path=cfg_path,
        )
        models = list_models(cfg_path=cfg_path)
        custom = [m for m in models if m["id"] == "user-added"]
        assert custom[0].get("custom") is True


class TestCouncilFallback:
    def test_single_model_uses_personas(self):
        from maggy.services.model_registry import (
            build_council_reviewers,
        )
        reviewers = build_council_reviewers(
            available_models=["claude"],
        )
        assert len(reviewers) >= 3
        for r in reviewers:
            assert "persona" in r or "model" in r

    def test_multi_model_uses_models(self):
        from maggy.services.model_registry import (
            build_council_reviewers,
        )
        reviewers = build_council_reviewers(
            available_models=["claude", "deepseek-pro", "kimi"],
        )
        models_used = {r["model"] for r in reviewers}
        assert len(models_used) > 1

    def test_two_models_mixes(self):
        from maggy.services.model_registry import (
            build_council_reviewers,
        )
        reviewers = build_council_reviewers(
            available_models=["claude", "codex"],
        )
        assert len(reviewers) >= 3
