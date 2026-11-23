"""Scrubbed environments for worker and check processes (RFC §2.3, §2.6.1, §2.6.7).

The runner keeps its full environment; children get an allowlist only.

- Worker env: the allowlist plus the adapter's declared provider key(s), when present in the
  runner's env. HOME stays the real one so the CLI can read its own login (e.g.
  ~/.codex/auth.json, Claude's credential store). Auth files are referenced read-only in
  place (`auth_file_refs`); the runner never copies them into the workspace.
- Check env: the allowlist with no credentials at all and HOME set to a throwaway dir the
  caller creates, so candidate code cannot read any login from the real HOME.

Toolchain vars (NVM_DIR, PYENV_ROOT, ...) are deliberately left out: the CLIs and checks
resolve node/python through PATH, which is kept.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from maggy.worker.adapter_spec import AdapterSpec
from maggy.worker.env_rules import looks_secret

ALLOWED_NAMES = frozenset({"PATH", "HOME", "LANG", "TERM", "TMPDIR", "SHELL", "USER"})
ALLOWED_PREFIXES = ("LC_",)


@dataclass(frozen=True)
class AuthFileRef:
    path: Path
    read_only: bool = True


def build_worker_env(adapter: AdapterSpec, base_env: Mapping[str, str]) -> dict[str, str]:
    """Allowlisted vars plus the adapter's declared provider keys; nothing else."""
    keys = {key: base_env[key] for key in adapter.env.provider_keys if key in base_env}
    return {**_allowlisted(base_env), **keys}


def build_check_env(base_env: Mapping[str, str], home: str) -> dict[str, str]:
    """Allowlisted vars only (no credentials, no provider keys), HOME = throwaway `home`."""
    return {**_allowlisted(base_env), "HOME": home}


def with_path_prefix(env: dict[str, str], prefix: Path | None) -> dict[str, str]:
    """`env` with `prefix` searched first on PATH (replay's fake CLIs); None: unchanged."""
    if prefix is None:
        return env
    return {**env, "PATH": os.pathsep.join([str(prefix), env.get("PATH", "")])}


def auth_file_refs(adapter: AdapterSpec, home: str) -> list[AuthFileRef]:
    """The adapter's auth files resolved against `home`, as read-only references."""
    return [AuthFileRef(Path(home) / path[2:] if path.startswith("~/") else Path(path))
            for path in adapter.env.auth_files]


def _allowlisted(base_env: Mapping[str, str]) -> dict[str, str]:
    return {key: value for key, value in base_env.items()
            if _allowed(key) and not looks_secret(key)}


def _allowed(name: str) -> bool:
    return name in ALLOWED_NAMES or name.startswith(ALLOWED_PREFIXES)
