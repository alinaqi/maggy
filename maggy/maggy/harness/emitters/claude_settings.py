"""Claude settings.json managed keys: hooks per event and permission rules.

Each managed key holds the user's own entries plus Maggy's. Maggy hook
entries are recognised by their command prefix, so dropping a hook from the
profile removes only Maggy's entry. Permission rules are added, never removed
(an emitted rule cannot be told apart from one the user wrote).
"""

from __future__ import annotations

import json
from pathlib import Path

from maggy.harness.emitters.permissions import claude_rules
from maggy.harness.emitters.sources import safe_name
from maggy.harness.fs_safe import read_text
from maggy.harness.schema import HarnessProfile
from maggy.harness.schema_sections import Hooks

HOOK_PREFIX = "$HOME/.maggy/hooks/"
EVENTS = {
    "session_start": ("SessionStart", None),
    "before_tool": ("PreToolUse", "*"),
    "after_tool": ("PostToolUse", "*"),
    "after_edit": ("PostToolUse", "Edit|Write|MultiEdit|NotebookEdit"),
    "before_stop": ("Stop", None),
    "before_compact": ("PreCompact", None),
    "session_end": ("SessionEnd", None),
}
ORDER = list(dict.fromkeys(event for event, _ in EVENTS.values()))


def load_settings(path: Path) -> dict:
    """Existing settings, or {} (an unparseable file is reported by plan_files)."""
    try:
        data = json.loads(read_text(path) or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _entry(field: str, names: list[str]) -> dict:
    _, matcher = EVENTS[field]
    cmds = [{"type": "command", "command": HOOK_PREFIX + safe_name(f"hooks.{field}", n)} for n in names]
    return {"matcher": matcher, "hooks": cmds} if matcher else {"hooks": cmds}


def maggy_hooks(hooks: Hooks) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for field, (event, _) in EVENTS.items():
        names = getattr(hooks, field)
        if names:
            out.setdefault(event, []).append(_entry(field, names))
    return out


def _is_maggy(entry: object) -> bool:
    cmds = entry.get("hooks") if isinstance(entry, dict) else None
    return bool(cmds) and all(str(c.get("command", "")).startswith(HOOK_PREFIX)
                              for c in cmds if isinstance(c, dict))


def hook_regions(hooks: Hooks, settings: dict) -> dict[str, list]:
    ours = maggy_hooks(hooks)
    disk = settings.get("hooks") if isinstance(settings.get("hooks"), dict) else {}
    current = {e: v for e, v in disk.items() if isinstance(v, list)}
    events = [e for e in ORDER if e in ours or any(map(_is_maggy, current.get(e, [])))]
    return {f"hooks.{e}": [x for x in current.get(e, []) if not _is_maggy(x)] + ours.get(e, [])
            for e in events}


def permission_regions(profile: HarnessProfile, settings: dict) -> dict[str, list]:
    perms = settings.get("permissions") if isinstance(settings.get("permissions"), dict) else {}
    out = {}
    for key, rules in claude_rules(profile).items():
        have = perms.get(key) if isinstance(perms.get(key), list) else []
        if rules:
            out[f"permissions.{key}"] = have + [r for r in rules if r not in have]
    return out


def settings_regions(profile: HarnessProfile, path: Path) -> dict[str, list]:
    settings = load_settings(path)
    return {**hook_regions(profile.hooks, settings), **permission_regions(profile, settings)}
