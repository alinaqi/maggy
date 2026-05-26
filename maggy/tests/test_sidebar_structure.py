"""Tests for sidebar menu structure — ensures pane/tab consistency."""
from pathlib import Path

import pytest

_STATIC = Path(__file__).parent.parent / "maggy" / "static"


def _read(name: str) -> str:
    return (_STATIC / name).read_text()


class TestProjectTabs:
    EXPECTED = ["chat", "inbox", "issues", "team", "cortex", "project-settings"]

    def test_all_present_in_html(self):
        html = _read("index.html")
        for tab in self.EXPECTED:
            assert f'data-tab="{tab}"' in html, f"Missing tab: {tab}"

    def test_removed_tabs_absent(self):
        html = _read("index.html")
        for old in ("followed", "progress", "icpg"):
            assert f'data-tab="{old}"' not in html, f"Stale tab: {old}"


class TestCommandCenterTabs:
    EXPECTED = ["skills", "plugins", "insights", "memory", "routing", "budget"]

    def test_all_present(self):
        html = _read("index.html")
        for tab in self.EXPECTED:
            assert f'data-tab="{tab}"' in html, f"Missing tab: {tab}"


class TestSystemTabs:
    EXPECTED = ["forge", "logs", "settings"]

    def test_all_present(self):
        html = _read("index.html")
        for tab in self.EXPECTED:
            assert f'data-tab="{tab}"' in html, f"Missing tab: {tab}"


class TestPaneConsistency:
    def test_every_tab_has_pane(self):
        html = _read("index.html")
        import re
        tabs = re.findall(r'data-tab="([^"]+)"', html)
        for tab in tabs:
            if tab == "chat":
                continue
            assert f'id="pane-{tab}"' in html, f"No pane for tab: {tab}"

    def test_no_stale_panes(self):
        html = _read("index.html")
        for old in ("pane-followed", "pane-progress", "pane-icpg"):
            assert f'id="{old}"' not in html, f"Stale pane: {old}"


class TestNoStandalonePluginPanes:
    def test_competitors_not_standalone(self):
        html = _read("index.html")
        assert 'data-tab="competitors"' not in html

    def test_build_in_public_not_standalone(self):
        html = _read("index.html")
        assert 'data-tab="build-in-public"' not in html
