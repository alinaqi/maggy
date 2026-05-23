"""Provider config — flex model routing with data sovereignty support.

Loads ~/.maggy/routing.yaml and exposes which bin script to use per tier.

Sovereignty modes:
  us    — US-based providers only (groq, together, anthropic, openai, google)
  local — local models only (ollama), no external API calls
  any   — no restrictions (includes deepseek, kimi, etc.)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from maggy.config import CONFIG_DIR

ROUTING_CONFIG_PATH = CONFIG_DIR / "routing.yaml"

BIN_DIR = Path(os.environ.get("MAGGY_BIN", str(Path.home() / "bin")))

SOVEREIGNTY_BLOCKED: dict[str, set[str]] = {
    "us": {"deepseek", "kimi", "moonshot"},
    "local": {"deepseek", "kimi", "moonshot", "groq", "together", "openai", "google", "anthropic"},
    "any": set(),
}

_PROVIDER_TO_BIN: dict[str, str] = {
    "groq": "groq",
    "together": "together",
    "ollama": "ollama-coder",
    "deepseek": "deepseek",
}

_SOVEREIGNTY_TIER_DEFAULTS: dict[str, dict[str, str]] = {
    "us": {"flash": "groq", "pro": "together"},
    "local": {"flash": "ollama", "pro": "ollama"},
    "any": {"flash": "groq", "pro": "together"},
}

_US_FALLBACK = {"flash": "groq", "pro": "together"}
_LOCAL_FALLBACK = {"flash": "ollama", "pro": "ollama"}


@dataclass
class ProviderSettings:
    model: str
    api_key_env: str = ""
    base_url: str = ""


_DEFAULT_PROVIDERS: dict[str, ProviderSettings] = {
    "groq": ProviderSettings(
        model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
    ),
    "together": ProviderSettings(
        model="meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
        api_key_env="TOGETHER_API_KEY",
    ),
    "ollama": ProviderSettings(
        model="qwen2.5-coder:72b",
        base_url="http://localhost:11434",
    ),
    "deepseek": ProviderSettings(
        model="deepseek-chat",
        api_key_env="DEEPSEEK_API_KEY",
    ),
}


@dataclass
class ProviderConfig:
    sovereignty: str = "us"
    tiers: dict[str, str] = field(default_factory=dict)
    providers: dict[str, ProviderSettings] = field(default_factory=dict)

    def __post_init__(self) -> None:
        defaults = _SOVEREIGNTY_TIER_DEFAULTS.get(self.sovereignty, _US_FALLBACK)
        for tier, provider in defaults.items():
            self.tiers.setdefault(tier, provider)
        for name, settings in _DEFAULT_PROVIDERS.items():
            self.providers.setdefault(name, settings)

    def is_allowed(self, provider: str) -> bool:
        blocked = SOVEREIGNTY_BLOCKED.get(self.sovereignty, set())
        return provider not in blocked

    def _resolve_provider(self, tier: str, fallback_map: dict[str, str]) -> str:
        provider = self.tiers.get(tier, fallback_map[tier])
        if not self.is_allowed(provider):
            provider = fallback_map[tier]
        return provider

    def flash_bin(self) -> str:
        if self.sovereignty == "local":
            return str(BIN_DIR / "ollama-coder")
        provider = self._resolve_provider("flash", _US_FALLBACK)
        bin_name = _PROVIDER_TO_BIN.get(provider, provider)
        return str(BIN_DIR / bin_name)

    def pro_bin(self) -> str:
        if self.sovereignty == "local":
            return str(BIN_DIR / "ollama-coder")
        provider = self._resolve_provider("pro", _US_FALLBACK)
        bin_name = _PROVIDER_TO_BIN.get(provider, provider)
        return str(BIN_DIR / bin_name)

    def flash_provider(self) -> str:
        if self.sovereignty == "local":
            return "ollama"
        return self._resolve_provider("flash", _US_FALLBACK)

    def pro_provider(self) -> str:
        if self.sovereignty == "local":
            return "ollama"
        return self._resolve_provider("pro", _US_FALLBACK)

    def flash_model(self) -> str:
        p = self.providers.get(self.flash_provider())
        return p.model if p else ""

    def pro_model(self) -> str:
        p = self.providers.get(self.pro_provider())
        return p.model if p else ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "sovereignty": self.sovereignty,
            "tiers": dict(self.tiers),
            "providers": {
                name: {
                    "model": s.model,
                    "api_key_env": s.api_key_env,
                    "base_url": s.base_url,
                }
                for name, s in self.providers.items()
            },
        }


def load_provider_config(path: Path | None = None) -> ProviderConfig:
    config_path = Path(path) if path else ROUTING_CONFIG_PATH
    if not config_path.exists():
        return ProviderConfig()

    try:
        raw = yaml.safe_load(config_path.read_text()) or {}
    except Exception:
        return ProviderConfig()

    sovereignty = raw.get("sovereignty", "us")
    tiers = dict(raw.get("tiers", {}))

    providers: dict[str, ProviderSettings] = {}
    for name, pdata in (raw.get("providers") or {}).items():
        providers[name] = ProviderSettings(
            model=pdata.get("model", _DEFAULT_PROVIDERS.get(name, ProviderSettings("")).model),
            api_key_env=pdata.get("api_key_env", ""),
            base_url=pdata.get("base_url", ""),
        )

    cfg = ProviderConfig(sovereignty=sovereignty, tiers=tiers, providers=providers)
    return cfg


def save_provider_config(cfg: ProviderConfig, path: Path | None = None) -> None:
    config_path = Path(path) if path else ROUTING_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.dump(cfg.to_dict(), default_flow_style=False))
