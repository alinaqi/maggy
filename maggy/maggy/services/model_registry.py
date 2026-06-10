"""User model registry — add, validate, remove custom AI models."""

from __future__ import annotations

import shutil
from pathlib import Path

from maggy.services.council_config import (
    ModelDef,
    load_council_config,
    save_council_config,
)

_BUILTIN_IDS = {
    "qwen3", "gemini-flash-lite", "deepseek-flash",
    "gemini-flash", "deepseek-pro", "gemini-cli", "agy",
    "kimi", "gemini-pro", "grok", "codex",
    "claude-sonnet", "claude-opus",
}

_PERSONAS = [
    {
        "persona": "security-reviewer",
        "system": "You are a security-focused code reviewer. "
        "Prioritize OWASP risks, auth flaws, injection.",
    },
    {
        "persona": "architecture-reviewer",
        "system": "You are a software architect reviewer. "
        "Evaluate modularity, coupling, scalability.",
    },
    {
        "persona": "pragmatist-reviewer",
        "system": "You are a pragmatic engineer reviewer. "
        "Focus on shipping speed, simplicity, test coverage.",
    },
]


def validate_model(
    access_type: str,
    cli_cmd: str = "",
    api_key: str = "",
    api_base: str = "",
) -> dict:
    if access_type == "cli":
        if not cli_cmd or not cli_cmd.strip():
            return {"valid": False, "error": "CLI command required"}
        binary = cli_cmd.strip().split()[0]
        expanded = str(Path(binary).expanduser())
        found = shutil.which(expanded) or (
            Path(expanded).is_file()
            and Path(expanded).stat().st_mode & 0o111
        )
        if not found:
            return {"valid": False, "error": f"Binary not found: {binary}"}
        return {"valid": True, "path": expanded}
    if access_type == "api":
        if not api_key or not api_key.strip():
            return {"valid": False, "error": "API key required"}
        return {"valid": True}
    return {"valid": False, "error": f"Unknown access type: {access_type}"}


def add_model(
    model_id: str,
    label: str,
    access_type: str,
    cli_cmd: str = "",
    api_key: str = "",
    api_base: str = "",
    tier: int = 99,
    cfg_path: Path | None = None,
) -> dict:
    if not model_id or not model_id.strip():
        return {"ok": False, "error": "Model ID required"}
    v = validate_model(access_type, cli_cmd, api_key, api_base)
    if not v.get("valid"):
        return {"ok": False, "error": v.get("error", "Validation failed")}
    cfg = load_council_config(cfg_path)
    if cfg.get_model(model_id):
        return {"ok": False, "error": f"Model '{model_id}' already exists"}
    cmd = cli_cmd.strip() if access_type == "cli" else None
    model = ModelDef(
        id=model_id, tier=tier,
        label=label, cmd=cmd,
    )
    cfg.models.append(model)
    save_council_config(cfg, cfg_path)
    result = model.to_dict()
    result["custom"] = True
    if access_type == "api" and api_key:
        result["has_api_key"] = True
    return {"ok": True, "model": result}


def remove_model(
    model_id: str,
    cfg_path: Path | None = None,
) -> dict:
    if model_id in _BUILTIN_IDS:
        return {"ok": False, "error": f"Cannot remove built-in model '{model_id}'"}
    cfg = load_council_config(cfg_path)
    before = len(cfg.models)
    cfg.models = [m for m in cfg.models if m.id != model_id]
    if len(cfg.models) == before:
        return {"ok": False, "error": f"Model '{model_id}' not found"}
    save_council_config(cfg, cfg_path)
    return {"ok": True}


def list_models(cfg_path: Path | None = None) -> list[dict]:
    cfg = load_council_config(cfg_path)
    result = []
    for m in cfg.models:
        d = m.to_dict()
        d["custom"] = m.id not in _BUILTIN_IDS
        result.append(d)
    return result


def build_routing_tiers(
    cfg_path: Path | None = None,
) -> list:
    from maggy.process.model_router import DEFAULT_TIERS
    from maggy.process.models import ModelTier
    cfg = load_council_config(cfg_path)
    builtin_names = {t.name for t in DEFAULT_TIERS}
    custom_tiers = []
    for m in cfg.models:
        if m.id in builtin_names:
            continue
        custom_tiers.append(ModelTier(
            name=m.id,
            provider="custom",
            model=m.id,
            cost_rank=m.tier,
            complexity_min=0,
            complexity_max=10,
            strengths=["custom"],
        ))
    return list(DEFAULT_TIERS) + custom_tiers


def build_council_reviewers(
    available_models: list[str],
) -> list[dict]:
    if len(available_models) == 0:
        return [
            {"model": "claude", "persona": p["persona"], "system": p["system"]}
            for p in _PERSONAS
        ]
    if len(available_models) == 1:
        model = available_models[0]
        return [
            {"model": model, "persona": p["persona"], "system": p["system"]}
            for p in _PERSONAS
        ]
    reviewers = []
    for i, persona in enumerate(_PERSONAS):
        model = available_models[i % len(available_models)]
        reviewers.append({"model": model, **persona})
    return reviewers
