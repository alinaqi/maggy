"""Telos + e2e-testkit routes: auth required, project_dir sandboxed."""

from __future__ import annotations

import plugin_route_helpers as helpers
import pytest

ROUTES = helpers.ROUTES
call = helpers.call
client = helpers.client
project = helpers.project
spawn = helpers.spawn


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("key", [None, "wrong"])
def test_unauthenticated_rejected(client, project, spawn, route, key):
    client.headers.pop("X-API-Key")
    if key:
        client.headers["X-API-Key"] = key
    resp = call(client, route, project)
    assert resp.status_code in (401, 403)
    assert not spawn[0].called and not spawn[1].called


def _outside_dirs(tmp_path, project):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = project / "escape"
    link.symlink_to(outside, target_is_directory=True)
    sibling = tmp_path / "registered-evil"
    sibling.mkdir()
    return [
        outside, project / ".." / "outside", f"{project}/../outside",
        link, sibling, "/", ".", "",
    ]


@pytest.mark.parametrize("route", ROUTES)
def test_outside_project_dir_rejected(client, project, spawn, tmp_path, route):
    for bad in _outside_dirs(tmp_path, project):
        resp = call(client, route, bad)
        assert resp.status_code in (400, 403), (bad, resp.text)
    assert not spawn[0].called and not spawn[1].called


def test_local_auth_mode_still_sandboxes(client, tmp_path, spawn):
    client.app.state.cfg.dashboard.auth_mode = "local"
    client.headers.pop("X-API-Key")
    resp = call(client, ROUTES[0], tmp_path)
    assert resp.status_code == 403
    assert not spawn[1].called
