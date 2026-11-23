"""Telos + e2e-testkit routes still work for a registered project."""

from __future__ import annotations

import plugin_route_helpers as helpers
import pytest

call = helpers.call
client = helpers.client
project = helpers.project
spawn = helpers.spawn


def test_telos_registered_project_works(client, project, spawn):
    resp = call(client, ("get", "/api/telos/status"), project)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    spawn[1].assert_called_once_with(str(project.resolve()))


def test_telos_registered_subdir_works(client, project, spawn):
    sub = project / "pkg"
    sub.mkdir()
    resp = call(client, ("get", "/api/telos/status"), sub)
    assert resp.status_code == 200


@pytest.mark.parametrize("url", ["/api/testkit/run", "/api/testkit/drift",
                                 "/api/testkit/intent"])
def test_testkit_registered_project_works(client, project, spawn, url):
    resp = call(client, ("post", url), project)
    assert resp.status_code == 200, resp.text


def test_testkit_run_uses_registered_cwd(client, project, spawn):
    resp = call(client, ("post", "/api/testkit/run"), project)
    assert resp.status_code == 200
    cwds = {c.kwargs.get("cwd") for c in spawn[0].call_args_list}
    assert cwds == {str(project.resolve())}


def test_testkit_history_registered_project(client, project, spawn):
    resp = call(client, ("get", "/api/testkit/history"), project)
    assert resp.status_code == 200
    assert "runs" in resp.json()
