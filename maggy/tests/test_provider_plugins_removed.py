"""Guard: the duplicate repo-root provider plugins stay deleted.

maggy/providers is the live tracker path; plugins/provider-{github,asana,
monday} only registered unused /api/provider/* routes and no-op polls.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.plugins import manager

REPO_PLUGINS = Path(__file__).resolve().parent.parent / "plugins"
DEAD_IDS = ["provider-github", "provider-asana", "provider-monday"]


@pytest.mark.parametrize("plugin_id", DEAD_IDS)
def test_provider_plugin_dir_is_gone(plugin_id):
    assert not (REPO_PLUGINS / plugin_id).exists()


def test_plugin_loader_discovers_no_provider_plugins(monkeypatch):
    monkeypatch.setattr(manager, "PLUGIN_DIRS", [REPO_PLUGINS])
    found = {m.id for m in manager.PluginManager().discover()}
    assert found.isdisjoint(DEAD_IDS)
