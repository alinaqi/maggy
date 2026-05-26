"""Tests for project-scoped data filtering."""

from pathlib import Path
import re

import pytest

_STATIC = Path(__file__).parent.parent / "maggy" / "static"


def _read_js() -> str:
    return (_STATIC / "app.js").read_text()


def _read_html() -> str:
    return (_STATIC / "index.html").read_text()


class TestGetProjectKeyHelper:
    def test_helper_defined(self):
        js = _read_js()
        assert "function getProjectKey()" in js

    def test_helper_reads_dom(self):
        js = _read_js()
        match = re.search(r"function getProjectKey\(\)\s*{[^}]+}", js)
        assert match, "getProjectKey body not found"
        body = match.group()
        assert "current-project-label" in body


class TestInboxProjectFiltering:
    def test_inbox_passes_project_param(self):
        js = _read_js()
        fn = _extract_function(js, "loadInbox")
        assert "getProjectKey()" in fn
        assert "?project=" in fn


class TestTeamProjectScoping:
    def test_team_uses_project_tasks_endpoint(self):
        js = _read_js()
        fn = _extract_function(js, "loadTeam")
        assert "/projects/" in fn
        assert "/tasks" in fn
        assert "getProjectKey()" in fn

    def test_team_requires_project(self):
        js = _read_js()
        fn = _extract_function(js, "loadTeam")
        assert "Select a project" in fn


class TestCortexProjectScoping:
    def test_cortex_auto_selects_project(self):
        js = _read_js()
        fn = _extract_function(js, "loadCortex")
        assert "getProjectKey()" in fn

    def test_cortex_resets_on_project_switch(self):
        js = _read_js()
        fn = _extract_function(js, "switchProject")
        assert "ICPG_PROJECT = null" in fn or "ICPG_PROJECT=null" in fn


class TestMemoryProjectScoping:
    def test_memory_passes_namespace(self):
        js = _read_js()
        fn = _extract_function(js, "loadMemory")
        assert "namespace=" in fn
        assert "getProjectKey()" in fn


class TestPluginEndpointUsesAppState:
    def test_routes_plugins_uses_app_state(self):
        src = (Path(__file__).parent.parent / "maggy" / "api" / "routes_plugins.py").read_text()
        assert "request.app.state" in src


class TestActivityEndpointProjectFilter:
    def test_activity_accepts_project_param(self):
        src = (Path(__file__).parent.parent / "maggy" / "api" / "routes.py").read_text()
        assert "project:" in src or "project :" in src
        assert "Query(" in src


def _extract_function(js: str, name: str) -> str:
    pattern = rf"(?:async\s+)?function\s+{name}\s*\("
    match = re.search(pattern, js)
    if not match:
        return ""
    start = match.start()
    depth = 0
    for i in range(start, len(js)):
        if js[i] == "{":
            depth += 1
        elif js[i] == "}":
            depth -= 1
            if depth == 0:
                return js[start : i + 1]
    return js[start:]
