"""HTTP client for Maggy REST API."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from urllib.parse import urlparse

import httpx
import typer

from maggy.config import CONFIG_DIR

DEFAULT_URL = "http://127.0.0.1:8080"
HEALTH_TIMEOUT = 2.0
START_WAIT = 45.0
START_POLL = 1.0


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

    def _get_port(self) -> int:
        parsed = urlparse(self.base_url)
        return parsed.port or 8080

    def _kill_stale_port(self) -> None:
        """Kill any process holding our port."""
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{self._get_port()}"],
                capture_output=True, text=True, timeout=5,
            )
        except (subprocess.SubprocessError, OSError):
            return
        for line in result.stdout.strip().splitlines():
            try:
                os.kill(int(line.strip()), signal.SIGTERM)
            except (ValueError, ProcessLookupError,
                    PermissionError):
                continue
        time.sleep(0.5)

    def _start_server(self) -> None:
        """Spawn server, logging to server.log."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        log = open(CONFIG_DIR / "server.log", "a")
        subprocess.Popen(
            [sys.executable, "-m", "maggy.main"],
            stdout=log, stderr=log,
        )

    def ensure_server(self) -> bool:
        """Return True if server is reachable."""
        if self._check_health():
            return True
        self._kill_stale_port()
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

    def routing_rules(self) -> dict:
        return self.get("/api/routing/rules")

    def budget_by_provider(self) -> list:
        return self.get("/api/budget/by-provider")

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

    # ── Chat ──────────────────────────────────────

    def chat_create(self, project_key: str) -> dict:
        return self.post(
            "/api/chat/sessions",
            {"project_key": project_key},
        )

    def chat_sessions(self) -> list:
        return self.get("/api/chat/sessions")

    def chat_history(self, session_id: str) -> dict:
        return self.get(f"/api/chat/sessions/{session_id}")

    def chat_send_stream(
        self, session_id: str, message: str,
    ):
        """Yield parsed SSE chunks from chat endpoint."""
        url = (
            f"{self.base_url}"
            f"/api/chat/sessions/{session_id}/send"
        )
        with httpx.stream(
            "POST", url,
            json={"message": message},
            timeout=120.0,
        ) as r:
            for line in r.iter_lines():
                if line.startswith("data: "):
                    yield json.loads(line[6:])

    def chat_send_routed(
        self, session_id: str, message: str,
        blast: int | None = None,
        allowed_models: list[str] | None = None,
    ):
        """Yield SSE chunks from routed chat endpoint."""
        url = (
            f"{self.base_url}"
            f"/api/chat/sessions/{session_id}/send-routed"
        )
        body: dict = {"message": message}
        if blast is not None:
            body["blast_score"] = blast
        if allowed_models:
            body["allowed_models"] = allowed_models
        with httpx.stream(
            "POST", url, json=body, timeout=120.0,
        ) as r:
            for line in r.iter_lines():
                if line.startswith("data: "):
                    yield json.loads(line[6:])

    def detect_project(self, cwd: str) -> str | None:
        """Match cwd (or any parent) against configured codebases."""
        from pathlib import Path
        try:
            cfg = self.config()
        except Exception:
            return None
        cwd_path = Path(cwd).resolve()
        for cb in cfg.get("codebases", []):
            root = Path(cb.get("path", "")).expanduser().resolve()
            try:
                cwd_path.relative_to(root)
                return cb.get("key")
            except ValueError:
                continue
        return None

    # ── Session management ─────────────────────────

    def spawn(self, task: str, project: str) -> dict:
        return self.post(
            "/api/execute",
            {"task_id": task, "mode": "tdd",
             "project_key": project},
        )

    def all_sessions(self) -> list:
        """Merge chat + executor sessions."""
        chat = self.chat_sessions()
        executor = self.sessions()
        combined = []
        for s in chat:
            combined.append({
                "id": s.get("id"),
                "project": s.get("project_key", ""),
                "model": "claude",
                "status": s.get("status", ""),
                "type": "chat",
                "messages": s.get("messages", 0),
            })
        for s in executor:
            combined.append({
                "id": s.get("id"),
                "project": s.get("task_id", ""),
                "model": s.get("model", "?"),
                "status": s.get("status", ""),
                "type": "executor",
                "messages": 0,
            })
        return combined

    def kill_session(self, session_id: str) -> dict:
        r = httpx.delete(
            f"{self.base_url}"
            f"/api/chat/sessions/{session_id}",
            timeout=10.0,
        )
        self._handle_error(r)
        return r.json()

    # ── Monitor ────────────────────────────────────

    def monitor_status(self) -> dict:
        return self.get("/api/monitor/status")

    def monitor_start(self) -> dict:
        return self.post("/api/monitor/start", {})

    def monitor_stop(self) -> dict:
        return self.post("/api/monitor/stop", {})

    # ── Health ─────────────────────────────────────

    def health_dashboard(self) -> dict:
        return self.get("/api/engram/diagnostics")

    def engram_diagnostics(self) -> dict:
        return self.get("/api/engram/diagnostics")
