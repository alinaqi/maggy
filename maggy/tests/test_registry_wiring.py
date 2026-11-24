"""Tests for model registry wiring into routing."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def cfg_path(tmp_path: Path) -> Path:
    return tmp_path / "council.yaml"


class TestRoutingWithCustomModels:
    def test_custom_model_appears_in_tiers(self, cfg_path):
        from maggy.services.model_registry import add_model
        from maggy.services.model_registry import build_routing_tiers
        add_model(
            model_id="my-llama", label="Llama",
            access_type="cli", cli_cmd="echo test",
            tier=5, cfg_path=cfg_path,
        )
        tiers = build_routing_tiers(cfg_path=cfg_path)
        names = [t.name for t in tiers]
        assert "my-llama" in names

    def test_builtin_tiers_preserved(self, cfg_path):
        from maggy.services.model_registry import build_routing_tiers
        tiers = build_routing_tiers(cfg_path=cfg_path)
        names = [t.name for t in tiers]
        assert "claude" in names or "local" in names

    def test_custom_tier_has_correct_rank(self, cfg_path):
        from maggy.services.model_registry import add_model
        from maggy.services.model_registry import build_routing_tiers
        add_model(
            model_id="cheap-local", label="Cheap",
            access_type="cli", cli_cmd="echo test",
            tier=2, cfg_path=cfg_path,
        )
        tiers = build_routing_tiers(cfg_path=cfg_path)
        custom = [t for t in tiers if t.name == "cheap-local"]
        assert custom[0].cost_rank == 2

    def test_no_duplicates_with_builtin(self, cfg_path):
        from maggy.services.model_registry import build_routing_tiers
        tiers = build_routing_tiers(cfg_path=cfg_path)
        names = [t.name for t in tiers]
        assert len(names) == len(set(names))


class TestBuiltinCouncilModelsAreNotCustomTiers:
    """Council default models are not user-added custom routing tiers.

    Regression: build_routing_tiers promoted every council default whose id is
    not a router tier name (qwen3 at tier 0, the claude-fable-5 chief) to a
    "custom" tier covering complexity 0-10, so qwen3 won every routing call.
    """

    def test_defaults_add_no_custom_tiers(self, cfg_path):
        from maggy.services.model_registry import build_routing_tiers
        tiers = build_routing_tiers(cfg_path=cfg_path)
        assert [t.name for t in tiers if t.provider == "custom"] == []

    def test_qwen3_default_never_routes(self, cfg_path):
        from maggy.services.model_registry import build_routing_tiers
        names = {t.name for t in build_routing_tiers(cfg_path=cfg_path)}
        assert "qwen3" not in names
        assert "claude-fable-5" not in names
