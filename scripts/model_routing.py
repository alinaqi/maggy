#!/usr/bin/env python3
"""Single source of truth for the user's preferred ("followed") model.

Auto-detects which models are usable on this machine (API keys, CLI
wrappers, local Ollama), resolves a primary + classifier, and persists the
choice to ~/.claude/model-config.json. All routing layers — srooter, the
route-task hooks, and Maggy — read from here instead of hardcoding a model.

CLI:
    model_routing.py detect          # print available logical models (json)
    model_routing.py show            # print the resolved config (json)
    model_routing.py get primary     # print one field (primary|classifier|mode)
    model_routing.py set-primary X   # set the followed model
    model_routing.py apply           # sync primary into srooter.yaml
    model_routing.py write-launcher deepseek  # ~/bin/claude-deepseek (direct)
    model_routing.py write-launchers          # all direct-capable launchers
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / ".claude" / "model-config.json"

# Logical model -> how to detect it and how each layer names it.
MODELS: dict[str, dict] = {
    "minimax": {"env": ["MINIMAX_API_KEY"], "cli": "minimax", "srooter": "minimax-m2.5"},
    "claude": {"env": ["ANTHROPIC_API_KEY", "CLAUDE_MAX_TOKEN"], "cli": "claude", "srooter": "claude-max"},
    "deepseek": {"env": ["DEEPSEEK_API_KEY"], "cli": "deepseek", "srooter": "deepseek-pro"},
    "kimi": {"env": ["MOONSHOT_API_KEY", "KIMI_API_KEY"], "cli": "kimi", "srooter": "kimi-k3"},
    "glm": {"env": ["GLM_API_KEY", "ZHIPUAI_API_KEY"], "cli": "glm", "srooter": "glm-5.3"},
    "gemini": {"env": ["GEMINI_API_KEY"], "cli": "gemini-api", "srooter": "gemini"},
    "grok": {"env": ["XAI_API_KEY", "GROK_API_KEY"], "cli": "grok", "srooter": "grok"},
    "qwen": {"env": [], "cli": "qwen3", "srooter": "qwen", "ollama": True},
    "codex": {"env": ["OPENAI_API_KEY"], "cli": "codex", "srooter": "codex"},
    "agy": {"env": [], "cli": "agy-delegate", "srooter": None},
}

# Preference order when auto-recommending (strong coding model first).
PRIMARY_PRIORITY = ["minimax", "claude", "deepseek", "kimi", "glm", "gemini", "grok", "codex", "qwen"]
# Classifier wants cheap/local first.
CLASSIFIER_PRIORITY = ["qwen", "deepseek", "kimi", "gemini"]

# Providers that expose a native Anthropic-compatible endpoint, so Claude Code
# can talk to them DIRECTLY (no srooter hop) via ANTHROPIC_BASE_URL. Codex is
# absent on purpose: OpenAI has no Anthropic Messages API, so it can only be
# reached through srooter's /anthropic->/v1/responses translation.
DIRECT: dict[str, dict] = {
    "deepseek": {"base_url": "https://api.deepseek.com/anthropic", "model": "deepseek-v4-pro"},
    "glm": {"base_url": "https://api.z.ai/api/anthropic", "model": "glm-5.3"},
    "kimi": {"base_url": "https://api.moonshot.ai/anthropic", "model": "kimi-k3"},
}


def _has_cli(name: str, which=shutil.which, bin_dir: Path | None = None) -> bool:
    """True if a CLI wrapper exists on PATH or in the user's bin dir."""
    bin_dir = (Path.home() / "bin") if bin_dir is None else bin_dir
    return bool(which(name)) or (bin_dir / name).exists()


# Files outside the current shell that may export provider keys.
_ENV_FILES = [
    Path.home() / ".zshrc",
    Path.home() / "Documents" / "AI-Playground" / "srooter" / ".srooter.local.env",
]


def collect_env() -> dict:
    """Merge os.environ with `export KEY=val` lines from known env files."""
    import re
    merged = dict(os.environ)
    for f in _ENV_FILES:
        try:
            for line in f.read_text().splitlines():
                m = re.match(r'\s*(?:export\s+)?([A-Z0-9_]+)=["\']?([^"\'\n]+)', line)
                if m:
                    merged.setdefault(m.group(1), m.group(2))
        except OSError:
            continue
    return merged


def _ollama_up(probe=None) -> bool:
    """Best-effort check that local Ollama is reachable."""
    if probe is not None:
        return probe()
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1)
        return True
    except Exception:
        return False


def detect_available(env: dict | None = None, which=shutil.which,
                     ollama=None, bin_dir: Path | None = None) -> dict[str, bool]:
    """Return {logical_model: usable} for every known model on this machine."""
    env = collect_env() if env is None else env
    out: dict[str, bool] = {}
    for name, spec in MODELS.items():
        has_key = any(env.get(k) for k in spec["env"])
        usable = has_key or _has_cli(spec["cli"], which, bin_dir)
        if spec.get("ollama"):
            usable = usable and _ollama_up(ollama)
        out[name] = bool(usable)
    return out


def _first_available(priority: list[str], available: dict[str, bool]) -> str | None:
    """First model in priority order that is available."""
    return next((m for m in priority if available.get(m)), None)


def recommend_primary(available: dict[str, bool]) -> str:
    """Pick the best followed model from what's available (claude is the floor)."""
    return _first_available(PRIMARY_PRIORITY, available) or "claude"


def recommend_classifier(available: dict[str, bool]) -> str:
    """Pick the cheapest available classifier (falls back to the primary)."""
    return _first_available(CLASSIFIER_PRIORITY, available) or recommend_primary(available)


def load(path: Path = CONFIG_PATH) -> dict:
    """Load the config, or {} if absent/corrupt."""
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def save(cfg: dict, path: Path = CONFIG_PATH) -> None:
    """Persist the config as pretty JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2) + "\n")


def ensure(path: Path = CONFIG_PATH, env: dict | None = None) -> dict:
    """Load existing config, or auto-detect and create one if missing/blank."""
    cfg = load(path)
    if cfg.get("primary"):
        return cfg
    available = detect_available(env)
    cfg.setdefault("enabled", {k: int(v) for k, v in available.items()})
    cfg["primary"] = recommend_primary(available)
    cfg["classifier"] = recommend_classifier(available)
    cfg.setdefault("mode", "smart")
    # Pre-analyze every prompt via minimax in the route-task hook.
    cfg.setdefault("analyze", True)
    cfg["auto_detected"] = True
    save(cfg, path)
    return cfg


def get_primary(path: Path = CONFIG_PATH, env: dict | None = None) -> str:
    """Convenience accessor used by routing layers."""
    return ensure(path, env).get("primary", "claude")


def srooter_id(logical: str) -> str | None:
    """Map a logical model to its srooter model id (None if not a gateway model)."""
    return MODELS.get(logical, {}).get("srooter")


def apply_to_srooter(cfg: dict, yaml_path: Path) -> bool:
    """Point srooter's real-coding routes (long_context + substantive) at the
    primary model, so switching actually moves the model Claude Code runs on.
    Best-effort."""
    sid = srooter_id(cfg.get("primary", ""))
    if not sid or not yaml_path.exists():
        return False
    import re
    text = yaml_path.read_text()
    new = text
    for route in ("long_context", "substantive"):
        new = re.sub(rf"(\n\s*{route}:\s*)\S+", rf"\g<1>{sid}", new, count=1)
    if new == text:
        return False
    yaml_path.write_text(new)
    return True


def direct_config(logical: str) -> dict | None:
    """Direct-provider connection for a logical model, or None if it can't be
    reached directly (unknown model, or no Anthropic-compatible endpoint like
    codex). Includes the token env-var candidates so the launcher can resolve a
    key at runtime."""
    d = DIRECT.get(logical)
    if not d:
        return None
    return {**d, "token_envs": MODELS.get(logical, {}).get("env", [])}


def _launcher_body(logical: str, cfg: dict, mr_path: str) -> str:
    """Bash for a claude-<backend> wrapper that points Claude Code straight at
    the provider's Anthropic-compatible endpoint."""
    envs = cfg["token_envs"]
    loop = "\n".join(f'  v="${{{k}:-}}"; if [ -n "$v" ]; then TOKEN="$v"; break; fi'
                     for k in envs) or '  :'
    return f"""#!/usr/bin/env bash
# Auto-generated by maggy model_routing.py (/model-config {logical} --direct).
# Launches Claude Code pointed directly at {logical} ({cfg['model']}),
# bypassing srooter. Regenerate: python3 {mr_path} write-launcher {logical}
set -euo pipefail

TOKEN=""
for _ in 1; do
{loop}
done
if [ -z "$TOKEN" ]; then
  echo "claude-{logical}: set one of: {', '.join(envs)}" >&2
  exit 1
fi

export ANTHROPIC_BASE_URL="{cfg['base_url']}"
export ANTHROPIC_AUTH_TOKEN="$TOKEN"
export ANTHROPIC_MODEL="{cfg['model']}"
export ANTHROPIC_SMALL_FAST_MODEL="{cfg['model']}"
exec claude "$@"
"""


def write_launcher(logical: str, bin_dir: Path | None = None,
                   mr_path: str | None = None) -> Path | None:
    """Write ~/bin/claude-<logical> for a direct-capable provider. Returns the
    path, or None if the model can't be launched directly."""
    cfg = direct_config(logical)
    if not cfg:
        return None
    bin_dir = bin_dir or (Path.home() / "bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    path = bin_dir / f"claude-{logical}"
    path.write_text(_launcher_body(logical, cfg, mr_path or __file__))
    path.chmod(0o755)
    return path


def _cmd_get(cfg: dict, args: list[str]) -> int:
    field = args[0] if args else "primary"
    print(cfg.get(field, ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = args[0] if args else "show"
    rest = args[1:]
    if cmd == "detect":
        print(json.dumps(detect_available(), indent=2))
    elif cmd == "ensure":
        # Create the config if missing (auto-detected); print the primary.
        print(ensure().get("primary", ""))
    elif cmd == "show":
        print(json.dumps(ensure(), indent=2))
    elif cmd == "get":
        return _cmd_get(ensure(), rest)
    elif cmd == "set-primary":
        if not rest:
            print("usage: set-primary <model>", file=sys.stderr)
            return 1
        cfg = ensure()
        cfg["primary"] = rest[0]
        cfg["auto_detected"] = False
        save(cfg)
        print(json.dumps(cfg, indent=2))
    elif cmd == "set-analyze":
        if not rest or rest[0] not in ("true", "false"):
            print("usage: set-analyze true|false", file=sys.stderr)
            return 1
        cfg = ensure()
        cfg["analyze"] = rest[0] == "true"
        save(cfg)
        print(f"analyze = {cfg['analyze']}")
    elif cmd == "apply":
        srooter = Path.home() / "Documents" / "AI-Playground" / "srooter" / "srooter.yaml"
        ok = apply_to_srooter(ensure(), srooter)
        print(f"srooter sync: {'ok' if ok else 'skipped'}")
    elif cmd == "write-launcher":
        if not rest:
            print("usage: write-launcher <deepseek|glm|kimi>", file=sys.stderr)
            return 1
        path = write_launcher(rest[0])
        if not path:
            print(f"{rest[0]}: no direct Anthropic endpoint "
                  f"(direct-capable: {', '.join(DIRECT)}). "
                  f"codex must route through srooter.", file=sys.stderr)
            return 1
        print(f"wrote {path} -> run `{path.name}` for a direct {rest[0]} session")
    elif cmd == "write-launchers":
        for logical in DIRECT:
            p = write_launcher(logical)
            print(f"wrote {p}")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
