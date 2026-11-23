"""A Maggy-generated pi extension that runs profile hooks on pi events.

pi 0.73.1 events (docs/extensions.md): session_start, tool_call (can block),
tool_result, agent_end, session_before_compact, session_shutdown. Each hook
runs $HOME/.maggy/hooks/<name> with no stdin payload; a non-zero exit blocks
the tool call only for before_tool. A missing hook script is ignored.
"""

from __future__ import annotations

import json

from maggy.harness.emitters.copies import CopyKind
from maggy.harness.emitters.sources import safe_name
from maggy.harness.schema_sections import Hooks

MARKER = "// maggy:managed-extension"
EXTENSION = CopyKind(marker=MARKER, rid="extension", label="pi extension file")

_TEMPLATE = """{marker}
// Maggy harness hooks for pi, generated from the harness profile; edits are reported as conflicts.
import {{ spawnSync }} from "node:child_process";
import {{ homedir }} from "node:os";
import {{ join }} from "node:path";

const HOOKS: Record<string, string[]> = {hooks};
const EDIT_TOOLS = new Set(["edit", "write"]);

function run(field: string): boolean {{
  for (const name of HOOKS[field] ?? []) {{
    const result = spawnSync(join(homedir(), ".maggy", "hooks", name), [], {{ stdio: "ignore" }});
    if (typeof result.status === "number" && result.status !== 0) return false;
  }}
  return true;
}}

export default function (pi: any) {{
  pi.on("session_start", async () => {{ run("session_start"); }});
  pi.on("tool_call", async () => (run("before_tool") ? undefined
    : {{ block: true, reason: "Maggy before_tool hook failed" }}));
  pi.on("tool_result", async (event: any) => {{
    run("after_tool");
    if (EDIT_TOOLS.has(event.toolName)) run("after_edit");
  }});
  pi.on("agent_end", async () => {{ run("before_stop"); }});
  pi.on("session_before_compact", async () => {{ run("before_compact"); }});
  pi.on("session_shutdown", async () => {{ run("session_end"); }});
}}
"""


def hooks_extension(hooks: Hooks) -> str | None:
    """The extension source, or None when the profile has no hooks."""
    table = {field: [safe_name(f"hooks.{field}", n) for n in names]
             for field, names in hooks.model_dump().items() if names}
    if not table:
        return None
    return _TEMPLATE.format(marker=MARKER, hooks=json.dumps(table, indent=2))
