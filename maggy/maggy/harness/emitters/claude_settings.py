"""Claude settings.json managed keys: hooks per event and permission rules.

Each is a list region (region_lists): the region holds only Maggy's entries
and harness.lock remembers them, so the user's own hooks and rules in the same
lists are kept and never conflict, and Maggy's earlier entries are replaced
when the profile changes (tightening a permission profile drops its broad
rules; dropping a hook drops its entry).
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


def hook_regions(hooks: Hooks) -> dict[str, list]:
    return {f"hooks.{event}[]": entries for event, entries in maggy_hooks(hooks).items()}


def permission_regions(profile: HarnessProfile) -> dict[str, list]:
    return {f"permissions.{key}[]": rules for key, rules in claude_rules(profile).items() if rules}


def settings_regions(profile: HarnessProfile) -> dict[str, list]:
    return {**hook_regions(profile.hooks), **permission_regions(profile)}
