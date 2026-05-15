"""Tests for DeepSeek V4 model routing integration."""

from __future__ import annotations

import pytest

from maggy.process.model_router import DEFAULT_TIERS, route_task


class TestTierStructure:
    def test_six_tiers_defined(self):
        assert len(DEFAULT_TIERS) == 6

    def test_tier_names(self):
        names = [t.name for t in DEFAULT_TIERS]
        assert "local" in names
        assert "deepseek-flash" in names
        assert "deepseek-pro" in names
        assert "kimi" in names
        assert "codex" in names
        assert "claude" in names

    def test_cost_rank_ordering(self):
        ranks = [t.cost_rank for t in DEFAULT_TIERS]
        assert ranks == sorted(ranks)

    def test_deepseek_flash_is_cheapest_api(self):
        flash = _tier("deepseek-flash")
        assert flash.cost_rank == 2

    def test_deepseek_pro_below_kimi(self):
        pro = _tier("deepseek-pro")
        kimi = _tier("kimi")
        assert pro.cost_rank < kimi.cost_rank

    def test_claude_is_most_expensive(self):
        claude = _tier("claude")
        assert claude.cost_rank == max(
            t.cost_rank for t in DEFAULT_TIERS
        )


class TestDeepSeekRouting:
    def test_low_complexity_routes_to_local(self):
        r = route_task(complexity_score=1)
        assert r.primary.name == "local"

    def test_medium_low_routes_to_deepseek_flash(self):
        r = route_task(complexity_score=4)
        assert r.primary.cost_rank <= 2

    def test_medium_routes_to_deepseek_pro(self):
        r = route_task(complexity_score=6)
        assert r.primary.name in (
            "deepseek-pro", "deepseek-flash",
        )

    def test_high_complexity_routes_premium(self):
        r = route_task(complexity_score=9)
        assert r.primary.cost_rank >= 3

    def test_security_skips_cheap_tiers(self):
        r = route_task(
            complexity_score=3, task_type="security",
        )
        assert r.primary.cost_rank >= 3

    def test_deepseek_flash_in_fallback_chain(self):
        r = route_task(complexity_score=1)
        assert "deepseek-flash" in r.fallback_chain


class TestDeepSeekProviders:
    def test_flash_provider(self):
        flash = _tier("deepseek-flash")
        assert flash.provider == "deepseek"

    def test_pro_provider(self):
        pro = _tier("deepseek-pro")
        assert pro.provider == "deepseek"


class TestDeepSeekStrengths:
    def test_flash_strengths(self):
        flash = _tier("deepseek-flash")
        assert "boilerplate" in flash.strengths

    def test_pro_strengths(self):
        pro = _tier("deepseek-pro")
        assert "code_generation" in pro.strengths


def _tier(name: str):
    for t in DEFAULT_TIERS:
        if t.name == name:
            return t
    raise ValueError(f"Tier {name!r} not found")
