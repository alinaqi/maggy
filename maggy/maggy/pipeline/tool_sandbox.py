"""Tool sandbox — path validation, symlink resolution, allowlist."""

from __future__ import annotations

from pathlib import Path

from maggy.pipeline.tool_schema import TOOL_ALLOWLIST, ToolCall

_SECRET_FILES = frozenset({
    ".env", ".env.local", ".env.production",
    "credentials.json", "secrets.yaml",
    "id_rsa", "id_ed25519",
})

_ALLOWED_DOTFILES = frozenset({".gitignore"})

_PATH_PARAMS = frozenset({"path"})


class ToolSandboxError(Exception):
    pass


class ToolSandbox:
    def __init__(self, working_dir: str) -> None:
        self._root = Path(working_dir).resolve()

    def validate_path(self, path: str) -> Path:
        resolved = (self._root / path).resolve()
        if not resolved.is_relative_to(self._root):
            raise ToolSandboxError(
                f"Path escapes sandbox: {path}",
            )
        name = resolved.name
        if name in _SECRET_FILES:
            raise ToolSandboxError(f"Secret file blocked: {name}")
        if name.startswith(".") and name not in _ALLOWED_DOTFILES:
            raise ToolSandboxError(f"Dotfile blocked: {name}")
        return resolved

    def validate_tool_call(self, call: ToolCall) -> ToolCall:
        if call.name not in TOOL_ALLOWLIST:
            raise ToolSandboxError(
                f"{call.name} not in allowlist",
            )
        for key in _PATH_PARAMS:
            if key in call.params:
                self.validate_path(call.params[key])
        return call
