"""Guard: unwired stub/duplicate shell scripts stay deleted.

scripts/convert-hooks-to-toml.sh duplicated the harness compiler's TOML
emitter; templates/mnemos-compact-recovery.sh was never wired into any
hook config (SessionStart restore is mnemos-session-start.sh).
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEAD_SCRIPTS = [
    "scripts/convert-hooks-to-toml.sh",
    "templates/mnemos-compact-recovery.sh",
]


@pytest.mark.parametrize("rel_path", DEAD_SCRIPTS)
def test_stub_script_is_gone(rel_path):
    assert (REPO_ROOT / "install.sh").exists()
    assert not (REPO_ROOT / rel_path).exists()


@pytest.mark.parametrize("rel_path", DEAD_SCRIPTS)
def test_hook_configs_do_not_reference_script(rel_path):
    name = Path(rel_path).name
    for config in ("templates/settings.json", "templates/config.toml"):
        assert name not in (REPO_ROOT / config).read_text()
