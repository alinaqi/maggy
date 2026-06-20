"""Tests for /api/pr-review/* routes."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from maggy.config import MaggyConfig
from maggy.review.models import BlastRadius, Finding, ReviewPlan, Severity, Verdict


@pytest.fixture()
def client():
    from maggy.main import create_app
    app = create_app()
    app.state.cfg = MaggyConfig()
    return TestClient(app)


def _fake_out():
    plan = ReviewPlan(blast_radius=BlastRadius(size="small"), council_size=2)
    finding = Finding(file="a.py", line=3, severity=Severity.blocking, title="bug", detail="x")
    final = Verdict(decision="changes_needed", summary="needs work", findings=[finding])
    return {"plan": plan, "chunks": [1], "final": final, "post": {"dry_run": True}, "cost": {"total_usd": 0.1}}


class TestLanguages:
    def test_lists_supported(self, client):
        resp = client.get("/api/pr-review/languages")
        assert resp.status_code == 200
        langs = resp.json()["languages"]
        assert {"python", "typescript", "go", "rust", "php"} <= set(langs)


class TestStatus:
    def test_status_shape(self, client):
        resp = client.get("/api/pr-review/status")
        assert resp.status_code == 200
        body = resp.json()
        assert "installed" in body and "languages" in body and "token_configured" in body


class TestRun:
    def test_missing_token_400(self, client, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        resp = client.post("/api/pr-review/run",
                           json={"owner": "o", "repo": "r", "pr_number": 1})
        assert resp.status_code == 400

    def test_run_serializes_verdict(self, client, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "tok")

        async def fake_run(owner, repo, num, **kw):
            assert kw["token"] == "tok"
            return _fake_out()

        with patch("maggy.review.pipeline.run_review", side_effect=fake_run):
            resp = client.post("/api/pr-review/run",
                               json={"owner": "o", "repo": "r", "pr_number": 7})
        assert resp.status_code == 200
        body = resp.json()
        assert body["decision"] == "changes_needed"
        assert body["dry_run"] is True
        assert len(body["findings"]) == 1
        assert body["findings"][0]["file"] == "a.py"

    def test_per_request_token_override(self, client, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        seen = {}

        async def fake_run(owner, repo, num, **kw):
            seen["token"] = kw["token"]
            return _fake_out()

        with patch("maggy.review.pipeline.run_review", side_effect=fake_run):
            resp = client.post("/api/pr-review/run",
                               json={"owner": "o", "repo": "r", "pr_number": 7,
                                     "github_token": "override_tok"})
        assert resp.status_code == 200
        assert seen["token"] == "override_tok"
