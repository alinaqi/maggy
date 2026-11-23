"""The Claude worker loads no settings-file plugins or hooks (RFC §2.6.1 invariant 1)."""

from __future__ import annotations

import pytest

from maggy.worker.launch import resolve_launch
from maggy.worker.templating import ArgvValues
from worker_launch_helpers import profile, shipped


@pytest.mark.parametrize("perm", ["read_only", "workspace"])
def test_claude_awg_off_loads_no_settings_file_plugins_or_hooks(perm):
    """User/project/local settings enable plugins (awg, clawalkietalkie) and hooks; an
    empty --setting-sources loads none of them (verified: meta.yaml `verified`)."""
    plan = resolve_launch(shipped("claude"), profile(allow_host=True), perm)
    argv = plan.argv(ArgvValues(prompt="p", workspace="/ws", permission=perm))
    assert argv[argv.index("--setting-sources") + 1] == ""
    assert argv.count("--setting-sources") == 1
