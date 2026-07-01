"""Visual regression tests for the Maggy dashboard.

These render the real dashboard in a headless browser and compare against golden
images in tests/visual/golden/. They are SKIPPED automatically when Playwright
or its browser binaries aren't installed, so the normal `pytest` run is never
blocked — install with `pip install maggy-harness[visual] && playwright install
chromium` to enable them.

Add a new visual check by calling `visual.snapshot("<name>")`; the first run
writes a candidate for you to review, then becomes the golden.
"""

from __future__ import annotations

import pytest

pytest.importorskip("playwright", reason="visual tests need [visual] extra")
pytest.importorskip("PIL")

# Skip the whole module if the chromium binary isn't installed.
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as _p:
        _exe = _p.chromium.executable_path
    import os
    if not os.path.exists(_exe):
        pytest.skip("chromium not installed (playwright install chromium)", allow_module_level=True)
except Exception:
    pytest.skip("playwright browser unavailable", allow_module_level=True)


def _open_dashboard(page, server, *, dark=True):
    """Navigate to the dashboard, dismiss the setup modal, settle."""
    page.goto(server.url, wait_until="networkidle")
    page.evaluate("() => document.documentElement.classList.toggle('light', %s)" % ("false" if dark else "true"))
    # remove any onboarding/setup overlay so shots are deterministic
    page.evaluate("() => document.querySelectorAll('#setup-modal-overlay,[id*=modal],[class*=overlay]').forEach(e=>e.remove())")
    page.wait_for_timeout(800)


class TestDashboardVisual:
    def test_dashboard_loads(self, visual, page, test_server):
        _open_dashboard(page, test_server)
        visual.snapshot("dashboard-home", full_page=False)

    def test_settings_tab(self, visual, page, test_server):
        _open_dashboard(page, test_server)
        page.evaluate("() => typeof switchTab==='function' && switchTab('settings')")
        page.wait_for_timeout(800)
        page.evaluate("() => document.querySelectorAll('[id*=modal],[class*=overlay]').forEach(e=>{if(getComputedStyle(e).position==='fixed')e.remove()})")
        visual.snapshot("settings-tab", full_page=False)
