"""Tests for ProviderConfig — flex routing + data sovereignty."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from maggy.provider_config import (
    ProviderConfig,
    load_provider_config,
    SOVEREIGNTY_BLOCKED,
)


class TestDefaults:
    def test_default_sovereignty_is_us(self):
        cfg = ProviderConfig()
        assert cfg.sovereignty == "us"

    def test_default_flash_is_groq(self):
        cfg = ProviderConfig()
        assert cfg.tiers["flash"] == "groq"

    def test_default_pro_is_together(self):
        cfg = ProviderConfig()
        assert cfg.tiers["pro"] == "together"

    def test_flash_bin_points_to_groq(self):
        cfg = ProviderConfig()
        assert cfg.flash_bin().endswith("groq")

    def test_pro_bin_points_to_together(self):
        cfg = ProviderConfig()
        assert cfg.pro_bin().endswith("together")


class TestSovereigntyUS:
    def test_us_blocks_deepseek(self):
        cfg = ProviderConfig(sovereignty="us")
        assert not cfg.is_allowed("deepseek")

    def test_us_blocks_kimi(self):
        cfg = ProviderConfig(sovereignty="us")
        assert not cfg.is_allowed("kimi")

    def test_us_allows_groq(self):
        cfg = ProviderConfig(sovereignty="us")
        assert cfg.is_allowed("groq")

    def test_us_allows_together(self):
        cfg = ProviderConfig(sovereignty="us")
        assert cfg.is_allowed("together")

    def test_us_allows_anthropic(self):
        cfg = ProviderConfig(sovereignty="us")
        assert cfg.is_allowed("anthropic")

    def test_us_allows_ollama(self):
        cfg = ProviderConfig(sovereignty="us")
        assert cfg.is_allowed("ollama")


class TestSovereigntyLocal:
    def test_local_blocks_deepseek(self):
        cfg = ProviderConfig(sovereignty="local")
        assert not cfg.is_allowed("deepseek")

    def test_local_blocks_groq(self):
        cfg = ProviderConfig(sovereignty="local")
        assert not cfg.is_allowed("groq")

    def test_local_blocks_together(self):
        cfg = ProviderConfig(sovereignty="local")
        assert not cfg.is_allowed("together")

    def test_local_blocks_anthropic(self):
        cfg = ProviderConfig(sovereignty="local")
        assert not cfg.is_allowed("anthropic")

    def test_local_allows_ollama(self):
        cfg = ProviderConfig(sovereignty="local")
        assert cfg.is_allowed("ollama")

    def test_local_flash_bin_is_ollama(self):
        cfg = ProviderConfig(sovereignty="local")
        assert cfg.flash_bin().endswith("ollama-coder")

    def test_local_pro_bin_is_ollama(self):
        cfg = ProviderConfig(sovereignty="local")
        assert cfg.pro_bin().endswith("ollama-coder")


class TestSovereigntyAny:
    def test_any_allows_deepseek(self):
        cfg = ProviderConfig(sovereignty="any")
        assert cfg.is_allowed("deepseek")

    def test_any_allows_kimi(self):
        cfg = ProviderConfig(sovereignty="any")
        assert cfg.is_allowed("kimi")

    def test_any_allows_groq(self):
        cfg = ProviderConfig(sovereignty="any")
        assert cfg.is_allowed("groq")


class TestLoadFromYaml:
    def test_load_sovereignty_local(self, tmp_path):
        f = tmp_path / "routing.yaml"
        f.write_text(textwrap.dedent("""
            sovereignty: local
            tiers:
              flash: ollama
              pro: ollama
        """))
        cfg = load_provider_config(f)
        assert cfg.sovereignty == "local"
        assert cfg.tiers["flash"] == "ollama"

    def test_load_sovereignty_us(self, tmp_path):
        f = tmp_path / "routing.yaml"
        f.write_text(textwrap.dedent("""
            sovereignty: us
            tiers:
              flash: groq
              pro: together
        """))
        cfg = load_provider_config(f)
        assert cfg.sovereignty == "us"
        assert cfg.tiers["pro"] == "together"

    def test_load_custom_provider_model(self, tmp_path):
        f = tmp_path / "routing.yaml"
        f.write_text(textwrap.dedent("""
            sovereignty: us
            tiers:
              flash: groq
              pro: together
            providers:
              groq:
                model: llama-3.1-70b-versatile
                api_key_env: GROQ_API_KEY
        """))
        cfg = load_provider_config(f)
        assert cfg.providers["groq"].model == "llama-3.1-70b-versatile"

    def test_load_missing_file_returns_defaults(self, tmp_path):
        cfg = load_provider_config(tmp_path / "nonexistent.yaml")
        assert cfg.sovereignty == "us"
        assert cfg.tiers["flash"] == "groq"

    def test_load_partial_yaml_uses_defaults_for_missing(self, tmp_path):
        f = tmp_path / "routing.yaml"
        f.write_text("sovereignty: us\n")
        cfg = load_provider_config(f)
        assert cfg.tiers["flash"] == "groq"
        assert cfg.tiers["pro"] == "together"


class TestBinResolution:
    def test_flash_deepseek_bin(self):
        cfg = ProviderConfig(sovereignty="any", tiers={"flash": "deepseek", "pro": "together"})
        assert cfg.flash_bin().endswith("deepseek")

    def test_pro_ollama_bin(self):
        cfg = ProviderConfig(sovereignty="any", tiers={"flash": "groq", "pro": "ollama"})
        assert cfg.pro_bin().endswith("ollama-coder")

    def test_sovereignty_local_overrides_tier_setting(self):
        # Even if tiers say groq, local sovereignty forces ollama
        cfg = ProviderConfig(sovereignty="local", tiers={"flash": "groq", "pro": "together"})
        assert cfg.flash_bin().endswith("ollama-coder")
        assert cfg.pro_bin().endswith("ollama-coder")

    def test_sovereignty_us_overrides_deepseek_tier(self):
        # US sovereignty + deepseek tier → falls back to groq
        cfg = ProviderConfig(sovereignty="us", tiers={"flash": "deepseek", "pro": "deepseek"})
        assert not cfg.flash_bin().endswith("deepseek")
        assert not cfg.pro_bin().endswith("deepseek")
