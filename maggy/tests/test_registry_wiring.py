"""Tests for model registry wiring into routing + deliberation."""

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


class TestDeliberationWithPersonas:
    @pytest.mark.asyncio
    async def test_persona_prompts_injected(self):
        from maggy.council.deliberation import Deliberation
        from maggy.council.models import ContextPackage

        captured: list[tuple[str, str]] = []

        async def spy_query(reviewer_id, prompt):
            captured.append((reviewer_id, prompt))
            return "APPROVE\nLooks good."

        reviewers = [
            {"model": "claude", "persona": "security", "system": "Focus on OWASP."},
            {"model": "claude", "persona": "architect", "system": "Evaluate modularity."},
            {"model": "claude", "persona": "pragmatist", "system": "Focus on shipping."},
        ]
        d = Deliberation(query_fn=spy_query)
        ctx = ContextPackage(
            goal="add endpoint", plan_text="GET /users",
            code_diff="+ route",
        )
        result = await d.run_with_personas(ctx, reviewers, threshold=2)
        assert result.approved
        assert len(captured) >= 3
        ids_used = {c[0] for c in captured}
        assert "security" in ids_used
        assert "architect" in ids_used

    @pytest.mark.asyncio
    async def test_persona_system_in_prompt(self):
        from maggy.council.deliberation import Deliberation
        from maggy.council.models import ContextPackage

        prompts_seen: list[str] = []

        async def spy_query(reviewer_id, prompt):
            prompts_seen.append(prompt)
            return "APPROVE\nOk."

        reviewers = [
            {"model": "m", "persona": "sec", "system": "Check for XSS."},
        ]
        d = Deliberation(query_fn=spy_query)
        ctx = ContextPackage(goal="g", plan_text="p", code_diff="d")
        await d.run_with_personas(ctx, reviewers, threshold=1)
        assert any("Check for XSS" in p for p in prompts_seen)

    @pytest.mark.asyncio
    async def test_fallback_to_plain_reviewers(self):
        from maggy.council.deliberation import Deliberation
        from maggy.council.models import ContextPackage

        async def mock_query(reviewer_id, prompt):
            return "APPROVE\nOk."

        d = Deliberation(query_fn=mock_query)
        ctx = ContextPackage(goal="g", plan_text="p", code_diff="d")
        result = await d.run(ctx, ["a", "b", "c"], threshold=2)
        assert result.approved
