"""Council of Experts configuration — load, validate, persist."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

_CONFIG_PATH = Path.home() / ".claude" / "council.yaml"

_DEFAULT_REVIEWERS: dict[str, list[dict]] = {
    "plan": [
        {"id": "deepseek-pro", "enabled": True},
        {"id": "codex", "enabled": True},
        {"id": "gemini-pro", "enabled": True},
    ],
    "review": [
        {"id": "deepseek-pro", "enabled": True},
        {"id": "kimi", "enabled": True},
        {"id": "codex", "enabled": False},
    ],
    "architecture": [
        {"id": "deepseek-pro", "enabled": True},
        {"id": "gemini-pro", "enabled": True},
        {"id": "grok", "enabled": True},
    ],
}

_DEFAULT_MODELS: list[dict] = [
    {"id": "qwen3", "cmd": "~/bin/qwen3", "tier": 0, "label": "Qwen3 (local)"},
    {"id": "gemini-flash-lite", "cmd": "~/bin/gemini-api --flash-lite", "tier": 1, "label": "Gemini Flash-Lite"},
    {"id": "deepseek-flash", "cmd": "~/bin/deepseek --flash", "tier": 2, "label": "DeepSeek Flash"},
    {"id": "gemini-flash", "cmd": "~/bin/gemini-api --flash", "tier": 3, "label": "Gemini Flash"},
    {"id": "deepseek-pro", "cmd": "~/bin/deepseek --pro", "tier": 4, "label": "DeepSeek Pro"},
    {"id": "gemini-cli", "cmd": "~/bin/gemini-cli --pro", "tier": 5, "label": "Gemini CLI"},
    {"id": "agy", "cmd": "~/bin/agy-delegate --print", "tier": 6, "label": "AGY"},
    {"id": "kimi", "cmd": "~/bin/kimi --quiet -p", "tier": 7, "label": "Kimi K2.6"},
    {"id": "gemini-pro", "cmd": "~/bin/gemini-api --pro-search", "tier": 8, "label": "Gemini Pro Search"},
    {"id": "grok", "cmd": "~/bin/grok", "tier": 9, "label": "Grok 4.3"},
    {"id": "codex", "cmd": "codex exec", "tier": 10, "label": "Codex"},
    {"id": "claude-sonnet", "cmd": None, "tier": 11, "label": "Claude Sonnet"},
    {"id": "claude-opus", "cmd": None, "tier": 12, "label": "Claude Opus"},
]


@dataclass
class ReviewerDef:
    id: str
    enabled: bool = True

    def to_dict(self) -> dict:
        return {"id": self.id, "enabled": self.enabled}


@dataclass
class ModelDef:
    id: str
    tier: int
    label: str
    cmd: str | None = None

    def to_dict(self) -> dict:
        return {"id": self.id, "cmd": self.cmd, "tier": self.tier, "label": self.label}

    def cmd_argv(self) -> list[str] | None:
        if not self.cmd:
            return None
        if isinstance(self.cmd, list):
            return list(self.cmd)
        parts = self.cmd.split()
        expanded = str(Path(parts[0]).expanduser())
        return [expanded] + parts[1:]


@dataclass
class CouncilConfig:
    enabled: bool = True
    threshold: int = 2
    auto_validate_plans: bool = True
    auto_review_architecture: bool = True
    auto_review_prs: bool = True
    reviewers: dict[str, list[ReviewerDef]] = field(default_factory=dict)
    models: list[ModelDef] = field(default_factory=list)

    def effective_threshold(self, reviewer_count: int) -> int:
        return max(1, min(self.threshold, reviewer_count))

    def get_reviewers(self, context: str) -> list[ReviewerDef]:
        return self.reviewers.get(context, [])

    def get_model(self, model_id: str) -> ModelDef | None:
        for m in self.models:
            if m.id == model_id:
                return m
        return None

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "threshold": self.threshold,
            "auto_validate_plans": self.auto_validate_plans,
            "auto_review_architecture": self.auto_review_architecture,
            "auto_review_prs": self.auto_review_prs,
            "reviewers": {
                ctx: [r.to_dict() for r in rs]
                for ctx, rs in self.reviewers.items()
            },
            "models": [m.to_dict() for m in self.models],
        }


def _parse_reviewers(raw: dict) -> dict[str, list[ReviewerDef]]:
    result: dict[str, list[ReviewerDef]] = {}
    for ctx, items in raw.items():
        result[ctx] = [
            ReviewerDef(id=r["id"], enabled=r.get("enabled", True))
            for r in items if isinstance(r, dict) and "id" in r
        ]
    return result


def _parse_models(raw: list) -> list[ModelDef]:
    return [
        ModelDef(
            id=m["id"],
            cmd=m.get("cmd"),
            tier=int(m.get("tier", 99)),
            label=m.get("label", m["id"]),
        )
        for m in raw if isinstance(m, dict) and "id" in m
    ]


def load_council_config(path: Path | None = None) -> CouncilConfig:
    path = path or _CONFIG_PATH
    if path.exists():
        try:
            data = yaml.safe_load(path.read_text()) or {}
            return CouncilConfig(
                enabled=data.get("enabled", True),
                threshold=data.get("threshold", 2),
                auto_validate_plans=data.get("auto_validate_plans", True),
                auto_review_architecture=data.get("auto_review_architecture", True),
                auto_review_prs=data.get("auto_review_prs", True),
                reviewers=_parse_reviewers(data.get("reviewers", _DEFAULT_REVIEWERS)),
                models=_parse_models(data.get("models", _DEFAULT_MODELS)),
            )
        except Exception:
            pass
    return CouncilConfig(
        reviewers=_parse_reviewers(_DEFAULT_REVIEWERS),
        models=_parse_models(_DEFAULT_MODELS),
    )


def save_council_config(cfg: CouncilConfig, path: Path | None = None) -> None:
    path = path or _CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(cfg.to_dict(), default_flow_style=False, sort_keys=False))
