"""Guard: the unregistered cortex-mcp server (and its Mnemos copy) stays deleted.

It was never wired into any MCP config, install.sh or the harness emitter;
scripts/mnemos is the kept Mnemos implementation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = ["README.md", "GETTING_STARTED.md", "install.sh"]


def test_cortex_mcp_directory_is_gone() -> None:
    assert (REPO_ROOT / "install.sh").exists()
    assert not (REPO_ROOT / "cortex-mcp").exists()


@pytest.mark.parametrize("rel_path", DOCS)
def test_docs_do_not_reference_cortex_mcp(rel_path: str) -> None:
    assert "cortex-mcp" not in (REPO_ROOT / rel_path).read_text()
