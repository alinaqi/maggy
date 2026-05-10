"""Tool registry — wraps mcp-forge's KNOWN_SERVERS.

Provides enable/disable per project and search capabilities
without requiring mcp-forge on PYTHONPATH.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ToolInfo:
    """A registered MCP tool."""

    slug: str
    mcp_url: str = ""
    has_mcp: str = "Community"
    auth_method: str = "API Key"
    enabled: bool = True


class ForgeRegistry:
    """Project-aware tool registry."""

    def __init__(self, forge_path: Path | None = None):
        self._tools: dict[str, ToolInfo] = {}
        self._forge_path = forge_path
        self._load_registry()

    def _load_registry(self) -> None:
        """Load from mcp-forge if available."""
        if not self._forge_path:
            return
        reg_file = self._forge_path / "src" / "mcp_registry.py"
        if not reg_file.exists():
            return
        # Parse KNOWN_SERVERS from the registry
        self._tools = _parse_registry(reg_file)

    def search(self, query: str) -> list[ToolInfo]:
        """Search tools by slug or keyword."""
        q = query.lower()
        return [
            t for t in self._tools.values()
            if q in t.slug or q in t.mcp_url.lower()
        ]

    def get(self, slug: str) -> ToolInfo | None:
        return self._tools.get(slug)

    def list_all(self) -> list[ToolInfo]:
        return list(self._tools.values())

    def set_enabled(self, slug: str, enabled: bool) -> bool:
        tool = self._tools.get(slug)
        if not tool:
            return False
        tool.enabled = enabled
        return True

    @property
    def count(self) -> int:
        return len(self._tools)


def _parse_registry(path: Path) -> dict[str, ToolInfo]:
    """Extract KNOWN_SERVERS entries from registry file."""
    tools: dict[str, ToolInfo] = {}
    content = path.read_text()
    # Find dict literals in KNOWN_SERVERS list
    import re
    pattern = r'\{[^}]+\}'
    for match in re.finditer(pattern, content):
        try:
            # Clean Python dict to JSON-compatible
            raw = match.group()
            raw = raw.replace("'", '"')
            data = json.loads(raw)
            slug = data.get("slug", "")
            if slug:
                tools[slug] = ToolInfo(
                    slug=slug,
                    mcp_url=data.get("mcp_url", ""),
                    has_mcp=data.get("has_mcp", "Community"),
                    auth_method=data.get("auth_method", ""),
                )
        except (json.JSONDecodeError, KeyError):
            continue
    return tools
