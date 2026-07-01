"""Fixtures for visual tests — app server, Playwright browser, VisualCheck.

Pattern: tests write `visual.snapshot("my-feature")` and golden images live
in tests/visual/golden/. First-run writes a candidate and xfails; subsequent
runs compare; --update-goldens accepts changes.
"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import uvicorn

if TYPE_CHECKING:
    from maggy.visual_check import VisualCheck


def _free_port() -> int:
    """Find a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _make_app():
    """Create a lightweight FastAPI app for visual testing.

    Uses a minimal app that serves ONLY the static dashboard files (index.html
    + /static/*) and a setup-status endpoint so the JS doesn't 404 on init.
    This avoids the full Maggy startup (codebase discovery, plugin loading,
    CLI scanning) which would make visual tests slow and flaky.
    """
    from fastapi import FastAPI
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    static_dir = Path(__file__).parent.parent.parent / "static"
    app = FastAPI(title="Maggy Visual Test")

    @app.get("/api/setup/status")
    async def _setup():
        return {"configured": True, "mode": "full"}

    @app.get("/api/chat/sessions")
    async def _sessions():
        return []

    @app.post("/api/chat/preload")
    async def _preload():
        return {"sessions": []}

    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/")
        async def _index():
            return FileResponse(str(static_dir / "index.html"),
                                headers={"Cache-Control": "no-store"})

        @app.get("/{name:path}")
        async def _catch(name: str):
            return FileResponse(str(static_dir / "index.html"),
                                headers={"Cache-Control": "no-store"})

    return app


class _Server:
    """A uvicorn server running in a daemon thread."""

    def __init__(self, app, port: int):
        self._port = port
        self._server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
        )
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._port}"

    def start(self) -> None:
        self._thread.start()
        for _ in range(40):
            try:
                s = socket.create_connection(("127.0.0.1", self._port), timeout=0.5)
                s.close()
                return
            except (ConnectionRefusedError, OSError):
                time.sleep(0.1)
        raise RuntimeError(f"Server did not start on port {self._port}")

    def stop(self) -> None:
        self._server.should_exit = True


@pytest.fixture(scope="module")
def test_server():
    """Start a Maggy app server on a free port for the module."""
    app = _make_app()
    port = _free_port()
    server = _Server(app, port)
    server.start()
    yield server
    server.stop()


@pytest.fixture()
def page(test_server, browser):
    """A Playwright page pointed at the test server."""
    pg = browser.new_page()
    pg.set_default_timeout(15000)
    yield pg
    pg.close()


@pytest.fixture(scope="module")
def browser():
    """A shared Playwright browser instance for the module."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture()
def visual(page) -> "VisualCheck":
    """Build a VisualCheck bound to the test page and standard golden dir."""
    from maggy.visual_check import VisualCheck
    return VisualCheck(page)
