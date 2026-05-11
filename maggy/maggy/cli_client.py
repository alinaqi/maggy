"""HTTP client for Maggy REST API."""

from __future__ import annotations

import subprocess
import sys
import time

import httpx
import typer

DEFAULT_URL = "http://127.0.0.1:8080"
HEALTH_TIMEOUT = 2.0
START_WAIT = 8.0
START_POLL = 0.5


class MaggyClient:
    """Thin wrapper over Maggy's REST API."""

    def __init__(self, base_url: str = DEFAULT_URL):
        self.base_url = base_url.rstrip("/")

    # ── Server lifecycle ─────────────────────────

    def _check_health(self) -> bool:
        try:
            r = httpx.get(
                f"{self.base_url}/api/health",
                timeout=HEALTH_TIMEOUT,
            )
            return r.status_code == 200
        except (httpx.ConnectError, httpx.ReadTimeout):
            return False

    def _start_server(self) -> None:
        subprocess.Popen(
            [sys.executable, "-m", "maggy.main"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def ensure_server(self) -> bool:
        """Return True if server is reachable."""
        if self._check_health():
            return True
        self._start_server()
        deadline = time.monotonic() + START_WAIT
        while time.monotonic() < deadline:
            time.sleep(START_POLL)
            if self._check_health():
                return True
        return False

    # ── API calls ────────────────────────────────

    def _handle_error(self, r: httpx.Response) -> None:
        if r.is_success:
            return
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        from rich.console import Console
        Console(stderr=True).print(
            f"[red]Error {r.status_code}:[/red] {detail}",
        )
        raise typer.Exit(1)

    def get(self, path: str, **params) -> dict | list:
        r = httpx.get(
            f"{self.base_url}{path}",
            params=params or None,
            timeout=30.0,
        )
        self._handle_error(r)
        return r.json()

    def post(self, path: str, body: dict) -> dict:
        r = httpx.post(
            f"{self.base_url}{path}",
            json=body,
            timeout=60.0,
        )
        self._handle_error(r)
        return r.json()

    def health(self) -> dict:
        return self.get("/api/health")

    def inbox(self, refresh: bool = False) -> dict:
        return self.get("/api/inbox", refresh=refresh)

    def activity(self) -> dict:
        return self.get("/api/activity")

    def route(self, blast: int, task_type: str) -> dict:
        return self.get(
            "/api/routing/decide",
            blast=blast,
            task_type=task_type,
        )

    def budget_summary(self) -> dict:
        return self.get("/api/budget")

    def competitors_news(self, limit: int = 50) -> list:
        return self.get("/api/competitors/news", limit=limit)

    def competitors_briefing(self) -> dict:
        return self.get("/api/competitors/news/summary")

    def models_heatmap(self) -> list:
        return self.get("/api/routing/heatmap")

    def process_health(self, project: str) -> dict:
        return self.get(f"/api/process/health/{project}")

    def config(self) -> dict:
        return self.get("/api/config")

    def execute(self, task_id: str, mode: str) -> dict:
        return self.post(
            "/api/execute",
            {"task_id": task_id, "mode": mode},
        )

    def sessions(self) -> list:
        return self.get("/api/execute/sessions")
