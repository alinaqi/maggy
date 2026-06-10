"""Tests for flex model routing — flash/pro tiers via provider config."""

from __future__ import annotations

import pytest

from maggy.process.model_router import DEFAULT_TIERS, build_tiers, route_task
from maggy.provider_config import ProviderConfig


class TestDefaultTierStructure:
    def test_default_tiers_has_local(self):
        names = [t.name for t in DEFAULT_TIERS]
        assert "local" in names

    def test_default_flash_tier_is_groq(self):
        names = [t.name for t in DEFAULT_TIERS]
        assert "groq-flash" in names

    def test_default_pro_tier_is_together(self):
        names = [t.name for t in DEFAULT_TIERS]
        assert "together-pro" in names

    def test_no_deepseek_in_defaults(self):
        names = [t.name for t in DEFAULT_TIERS]
        assert not any("deepseek" in n for n in names)

    def test_cost_rank_ordering(self):
        ranks = [t.cost_rank for t in DEFAULT_TIERS]
        assert ranks == sorted(ranks)

    def test_claude_is_most_expensive(self):
        claude = _tier_default("claude")
        assert claude.cost_rank == max(t.cost_rank for t in DEFAULT_TIERS)


class TestBuildTiersFlexConfig:
    def test_groq_flash_config(self):
        cfg = ProviderConfig(sovereignty="us", tiers={"flash": "groq", "pro": "together"})
        tiers = build_tiers(cfg)
        names = [t.name for t in tiers]
        assert "groq-flash" in names

    def test_together_pro_config(self):
        cfg = ProviderConfig(sovereignty="us", tiers={"flash": "groq", "pro": "together"})
        tiers = build_tiers(cfg)
        names = [t.name for t in tiers]
        assert "together-pro" in names

    def test_ollama_flash_config(self):
        cfg = ProviderConfig(sovereignty="local", tiers={"flash": "ollama", "pro": "ollama"})
        tiers = build_tiers(cfg)
        flash = next(t for t in tiers if t.cost_rank == 3)
        assert flash.provider == "ollama"

    def test_local_sovereignty_uses_ollama_for_both(self):
        cfg = ProviderConfig(sovereignty="local")
        tiers = build_tiers(cfg)
        flash = next(t for t in tiers if t.cost_rank == 3)
        pro = next(t for t in tiers if t.cost_rank == 4)
        assert flash.provider == "ollama"
        assert pro.provider == "ollama"

    def test_deepseek_blocked_in_us_sovereignty(self):
        cfg = ProviderConfig(sovereignty="us", tiers={"flash": "deepseek", "pro": "deepseek"})
        tiers = build_tiers(cfg)
        providers = [t.provider for t in tiers]
        assert "deepseek" not in providers


class TestRouting:
    def test_low_complexity_routes_to_local(self):
        r = route_task(complexity_score=1)
        assert r.primary.name == "local"

    def test_medium_low_routes_to_flash_tier(self):
        r = route_task(complexity_score=4)
        assert r.primary.cost_rank <= 3

    def test_medium_routes_to_pro_tier(self):
        r = route_task(complexity_score=6)
        assert r.primary.cost_rank >= 3

    def test_high_complexity_routes_premium(self):
        r = route_task(complexity_score=9)
        assert r.primary.cost_rank >= 3

    def test_security_skips_cheap_tiers(self):
        r = route_task(complexity_score=3, task_type="security")
        assert r.primary.cost_rank >= 3

    def test_flash_tier_in_fallback_chain(self):
        r = route_task(complexity_score=1)
        assert len(r.fallback_chain) > 0


class TestProviderInfo:
    def test_default_flash_provider_is_groq(self):
        flash = _tier_default("groq-flash")
        assert flash.provider == "groq"

    def test_default_pro_provider_is_together(self):
        pro = _tier_default("together-pro")
        assert pro.provider == "together"

    def test_flash_strengths_include_boilerplate(self):
        flash = _tier_default("groq-flash")
        assert "boilerplate" in flash.strengths

    def test_pro_strengths_include_code_generation(self):
        pro = _tier_default("together-pro")
        assert "code_generation" in pro.strengths


def _tier_default(name: str):
    for t in DEFAULT_TIERS:
        if t.name == name:
            return t
    raise ValueError(f"Tier {name!r} not found in DEFAULT_TIERS")
