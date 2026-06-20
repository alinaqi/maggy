"""Tools the reviewer/planner agents call to VERIFY against the real repo
instead of guessing — the core fix for the false-positive class."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from pydantic_ai import RunContext

from . import github


@dataclass
class ReviewDeps:
    token: str
    owner: str
    repo: str
    head_sha: str
    files: list[dict]                       # PR files (filename, patch, additions, deletions, status)
    local_path: Path | None = None          # local checkout for fast grep (optional)
    mcp_bin: str = ""                        # codebase-memory-mcp for query_icpg (optional)
    _cache: dict = field(default_factory=dict)


def register_tools(agent):
    """Attach the shared repo toolset to a Pydantic AI agent."""

    @agent.tool
    def list_changed_files(ctx: RunContext[ReviewDeps]) -> str:
        """List the files changed in this PR with +/- line counts and status."""
        return "\n".join(
            f"{f['filename']} ({f.get('status','')}, +{f.get('additions',0)}/-{f.get('deletions',0)})"
            for f in ctx.deps.files
        ) or "(no files)"

    @agent.tool
    def get_diff(ctx: RunContext[ReviewDeps], path: str) -> str:
        """Get the unified diff (patch) for one changed file."""
        for f in ctx.deps.files:
            if f["filename"] == path:
                return f.get("patch") or "(no textual patch — binary or too large)"
        return f"(no diff: {path} is not in this PR)"

    @agent.tool
    def read_file(ctx: RunContext[ReviewDeps], path: str) -> str:
        """Read the FULL current contents of a file at the PR head (to see
        unchanged code: helper definitions, imports, neighbours). Use this before
        claiming a symbol is undefined or a file is incomplete."""
        key = f"read:{path}"
        if key in ctx.deps._cache:
            return ctx.deps._cache[key]
        try:
            txt = github.get_file_at(ctx.deps.token, ctx.deps.owner, ctx.deps.repo, path, ctx.deps.head_sha)
        except Exception as e:  # noqa: BLE001
            txt = f"(could not read {path}: {e})"
        if len(txt) > 18000:
            txt = txt[:18000] + "\n... [truncated; ask for a grep if you need a later part] ..."
        ctx.deps._cache[key] = txt
        return txt

    @agent.tool
    def grep(ctx: RunContext[ReviewDeps], pattern: str, path_glob: str = "") -> str:
        """Search the repo for a regex (e.g. a symbol/def, a translation key, an
        import). Authoritative way to check whether something exists in unchanged
        code. Returns matching `file:line: text` lines."""
        lp = ctx.deps.local_path
        if not lp or not Path(lp).exists():
            return "(local repo not available for grep — use read_file on a specific path instead)"
        # pattern/path_glob are model-controlled (and the model can be
        # prompt-injected via the diff). Terminate options with `--` so a
        # leading-dash value can't be smuggled to grep as a flag.
        cmd = ["grep", "-rnI", "--exclude-dir=.git", "--exclude-dir=node_modules",
               "--exclude-dir=.venv", "-E"]
        if path_glob:
            cmd.append(f"--include={path_glob}")
        cmd += ["--", pattern, str(lp)]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout
        except Exception as e:  # noqa: BLE001
            return f"(grep failed: {e})"
        lines = [ln.replace(str(lp) + "/", "") for ln in out.splitlines()][:40]
        return "\n".join(lines) or f"(no matches for /{pattern}/)"

    @agent.tool
    def read_adr(ctx: RunContext[ReviewDeps], query: str) -> str:
        """Search the repo's docs/ADRs for an Accepted decision before flagging or
        clearing an ADR concern. Returns matching ADR files + lines."""
        lp = ctx.deps.local_path
        if not lp:
            return "(local repo not available)"
        adr_dir = Path(lp) / "docs/ADRs"
        if not adr_dir.exists():
            return "(no docs/ADRs/ in this repo)"
        hits = []
        for p in sorted(adr_dir.glob("*.md")):
            for i, ln in enumerate(p.read_text(errors="replace").splitlines(), 1):
                if query.lower() in ln.lower():
                    hits.append(f"{p.name}:{i}: {ln.strip()[:120]}")
        return "\n".join(hits[:30]) or f"(no ADR mentions '{query}')"

    return agent
