"""Full API endpoint validation tests.

Creates a real FastAPI app with all services wired in
(using tmp directories for SQLite) and validates every
endpoint from all 14 phases.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from maggy.budget import BudgetManager
from maggy.cikg.graph import KnowledgeGraphService
from maggy.cikg.models import Edge, Node
from maggy.config import (
    BudgetConfig,
    DashboardConfig,
    MaggyConfig,
    MeshConfig,
    RoutingConfig,
    StorageConfig,
)
from maggy.deploy import DeployService
from maggy.engram.record import EngramRecord
from maggy.engram.store import EngramStore
from maggy.event_spine.emitter import EventEmitter
from maggy.event_spine.events import IntentEvent
from maggy.event_spine.store import EventStore
from maggy.forge.connector import ForgeConnector
from maggy.lexon.router import LexonRouter
from maggy.mesh.manager import MeshManager
from maggy.mesh.store import MeshStore
from maggy.planning import PlanningService
from maggy.history.service import HistoryService
from maggy.improve.service import Introspector
from maggy.routing import RoutingService


@pytest.fixture
def app_with_services(tmp_path: Path) -> FastAPI:
    """Build a FastAPI app with all services wired."""
    cfg = MaggyConfig(
        storage=StorageConfig(path=str(tmp_path / "store.db")),
        dashboard=DashboardConfig(auth_mode="local"),
        budget=BudgetConfig(daily_limit_usd=10.0),
        routing=RoutingConfig(),
        mesh=MeshConfig(enabled=True),
    )

    app = FastAPI()
    app.state.cfg = cfg
    app.state.configured = True
    app.state.mode = "local"

    # Wire all services
    app.state.budget = BudgetManager(cfg)
    app.state.routing = RoutingService(cfg)
    app.state.events = EventEmitter(
        EventStore(tmp_path / "events.db"),
    )
    app.state.cikg = KnowledgeGraphService(
        tmp_path / "cikg.db",
    )
    app.state.planning = PlanningService(cfg)
    app.state.deploy = DeployService()
    app.state.forge = ForgeConnector(
        forge_path=tmp_path / "fake-forge",
    )
    app.state.engram = EngramStore(tmp_path / "engram.db")
    app.state.lexon = LexonRouter()

    mesh_store = MeshStore(tmp_path / "mesh.db")
    mesh_cfg = SimpleNamespace(
        peer_id="test-peer",
        org_key_secret="secret",
        port=8080,
        tunnel_url="",
        git_discovery=False,
    )
    mgr = MeshManager(mesh_cfg, mesh_store)
    mgr.add_network("test-org")
    app.state.mesh = mgr
    app.state.history = HistoryService(
        db_path=tmp_path / "history.db",
        cli_dirs={
            "claude": tmp_path / "no_claude",
            "codex": tmp_path / "no_codex",
            "kimi": tmp_path / "no_kimi",
        },
    )
    app.state.introspector = Introspector(app.state)
    app.state.heartbeat = None

    # Register all routers
    from maggy.api.routes import router as r_api
    from maggy.api.routes_budget import router as r_budget
    from maggy.api.routes_cikg import router as r_cikg
    from maggy.api.routes_deploy import router as r_deploy
    from maggy.api.routes_engram import router as r_engram
    from maggy.api.routes_events import router as r_events
    from maggy.api.routes_forge import router as r_forge
    from maggy.api.routes_heartbeat import router as r_heartbeat
    from maggy.api.routes_history import router as r_history
    from maggy.api.routes_improve import router as r_improve
    from maggy.api.routes_lexon import router as r_lexon
    from maggy.api.routes_mesh import router as r_mesh
    from maggy.api.routes_planning import router as r_plan
    from maggy.api.routes_routing import router as r_routing
    from maggy.api.routes_setup import router as r_setup
    from maggy.api.routes_users import router as r_users

    for r in (
        r_api, r_budget, r_cikg, r_deploy, r_engram,
        r_events, r_forge, r_heartbeat, r_history,
        r_improve, r_lexon, r_mesh, r_plan, r_routing,
        r_setup, r_users,
    ):
        app.include_router(r)

    return app


@pytest.fixture
def client(app_with_services: FastAPI) -> TestClient:
    return TestClient(app_with_services)


# ── Phase 1: Budget ─────────────────────────────────────


class TestBudgetAPI:
    def test_get_budget_empty(self, client: TestClient):
        resp = client.get("/api/budget")
        assert resp.status_code == 200
        data = resp.json()
        assert "daily_limit_usd" in data
        assert "spent_today_usd" in data
        assert data["spent_today_usd"] == 0.0

    def test_budget_by_provider_empty(self, client: TestClient):
        resp = client.get("/api/budget/by-provider")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_budget_with_spend(
        self, app_with_services: FastAPI,
    ):
        mgr = app_with_services.state.budget
        mgr.record_spend("anthropic", "claude", 2.5)
        mgr.record_spend("openai", "gpt-4", 1.0)

        c = TestClient(app_with_services)
        resp = c.get("/api/budget")
        data = resp.json()
        assert data["spent_today_usd"] == 3.5

        resp = c.get("/api/budget/by-provider")
        providers = {
            r["provider"]: r["spent_usd"]
            for r in resp.json()
        }
        assert providers["anthropic"] == 2.5
        assert providers["openai"] == 1.0


# ── Phase 2: Routing ────────────────────────────────────


class TestRoutingAPI:
    def test_heatmap_empty(self, client: TestClient):
        resp = client.get("/api/routing/heatmap")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_decide_low_blast(self, client: TestClient):
        resp = client.get(
            "/api/routing/decide?blast=1&task_type=bugfix",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "primary" in data
        assert "reason" in data

    def test_decide_high_blast(self, client: TestClient):
        resp = client.get(
            "/api/routing/decide?blast=9&task_type=feature",
        )
        data = resp.json()
        assert data["primary"] is not None

    def test_heatmap_after_recording(
        self, app_with_services: FastAPI,
    ):
        svc = app_with_services.state.routing
        svc.record_outcome("claude", "feature", 5, 0.9)
        c = TestClient(app_with_services)
        resp = c.get("/api/routing/heatmap")
        assert len(resp.json()) >= 1


class TestUsersAPI:
    def test_create_user(self, client: TestClient):
        resp = client.post(
            "/api/users",
            json={"email": "user@example.com", "password": "secret123"},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "user@example.com"
        assert "password_hash" not in data


# ── Phase 14: Event Spine ───────────────────────────────


class TestEventsAPI:
    def test_events_empty(self, client: TestClient):
        resp = client.get("/api/events")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_event_count_empty(self, client: TestClient):
        resp = client.get("/api/events/count")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_trace_empty(self, client: TestClient):
        resp = client.get("/api/events/trace/nope")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_events_after_emit(
        self, app_with_services: FastAPI,
    ):
        emitter = app_with_services.state.events
        evt = IntentEvent(
            intent_text="Add login",
            decomposed_steps=["create form", "add auth"],
        )
        evt.header.task_id = "t-1"
        emitter.emit(evt)

        c = TestClient(app_with_services)
        resp = c.get("/api/events?task_id=t-1")
        assert len(resp.json()) == 1

        resp = c.get("/api/events/trace/t-1")
        assert len(resp.json()) == 1

        resp = c.get("/api/events/count")
        assert resp.json()["count"] == 1


# ── Phase 4: CIKG ───────────────────────────────────────


class TestCIKGAPI:
    def test_landscape_empty(self, client: TestClient):
        resp = client.get("/api/cikg/landscape")
        assert resp.status_code == 200
        data = resp.json()
        assert data["competitors"] == 0

    def test_gaps_no_feature(self, client: TestClient):
        resp = client.get("/api/cikg/gaps/SSO")
        assert resp.status_code == 200
        data = resp.json()
        assert "gap_count" in data

    def test_landscape_with_data(
        self, app_with_services: FastAPI,
    ):
        graph = app_with_services.state.cikg
        graph.add_node(Node(
            id="c1", node_type="competitor", name="Rival",
        ))
        graph.add_node(Node(
            id="f1", node_type="feature", name="SSO",
        ))
        graph.add_edge(Edge("c1", "f1", "has_feature"))

        c = TestClient(app_with_services)
        resp = c.get("/api/cikg/landscape")
        data = resp.json()
        assert data["competitors"] == 1
        assert data["features_tracked"] == 1

        resp = c.get("/api/cikg/gaps/SSO")
        data = resp.json()
        assert data["feature"] == "SSO"


# ── Phase 6: Planning ───────────────────────────────────


class TestPlanningAPI:
    def test_single_plan(self, client: TestClient):
        resp = client.post(
            "/api/planning/generate",
            json={"task": "Add auth", "blast_score": 2},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "single"
        assert len(data["plan"]["steps"]) == 3

    def test_dual_plan(self, client: TestClient):
        resp = client.post(
            "/api/planning/generate",
            json={"task": "Refactor core", "blast_score": 7},
        )
        data = resp.json()
        assert data["mode"] == "dual"
        assert "diff" in data


# ── Phase 7: Deploy ─────────────────────────────────────


class TestDeployAPI:
    def test_sessions_empty(self, client: TestClient):
        resp = client.get("/api/deploy/sessions")
        assert resp.status_code == 200
        assert resp.json()["sessions"] == []

    def test_create_and_get(self, client: TestClient):
        resp = client.post(
            "/api/deploy/sessions",
            json={"project": "web", "branch": "feat-x"},
        )
        assert resp.status_code == 200
        data = resp.json()
        sid = data["session_id"]
        assert data["status"] == "building"

        resp = client.get(f"/api/deploy/sessions/{sid}")
        assert resp.json()["project"] == "web"

    def test_missing_session(self, client: TestClient):
        resp = client.get("/api/deploy/sessions/nope")
        data = resp.json()
        assert data.get("error") == "session not found"


# ── Phase 9: Forge ──────────────────────────────────────


class TestForgeAPI:
    def test_forge_status(self, client: TestClient):
        resp = client.get("/api/forge/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data
        assert "registry_count" in data

    def test_forge_search(self, client: TestClient):
        resp = client.get("/api/forge/search?q=test")
        assert resp.status_code == 200
        assert "results" in resp.json()

    def test_forge_gaps_empty(self, client: TestClient):
        resp = client.get("/api/forge/gaps")
        assert resp.status_code == 200
        assert resp.json()["gaps"] == []

    def test_report_gap(self, client: TestClient):
        resp = client.post(
            "/api/forge/gaps",
            json={"capability": "slack-notify"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["capability"] == "slack-notify"

        resp = client.get("/api/forge/gaps")
        gaps = resp.json()["gaps"]
        assert len(gaps) == 1


# ── Phase 12: Engram ────────────────────────────────────


class TestEngramAPI:
    def test_query_empty(self, client: TestClient):
        resp = client.get("/api/engram/query")
        assert resp.status_code == 200
        assert resp.json()["records"] == []

    def test_diagnostics_empty(self, client: TestClient):
        resp = client.get("/api/engram/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_memories" in data

    def test_query_with_data(
        self, app_with_services: FastAPI,
    ):
        store = app_with_services.state.engram
        store.write(EngramRecord(
            engram_id="e1",
            namespace="test",
            memory_type="fact",
            content="Test memory",
            tags=["test"],
        ))

        c = TestClient(app_with_services)
        resp = c.get("/api/engram/query?namespace=test")
        records = resp.json()["records"]
        assert len(records) == 1
        assert records[0]["content"] == "Test memory"

    def test_diagnostics_with_data(
        self, app_with_services: FastAPI,
    ):
        store = app_with_services.state.engram
        store.write(EngramRecord(
            engram_id="e2",
            namespace="test",
            memory_type="decision",
            content="Chose X over Y",
        ))

        c = TestClient(app_with_services)
        resp = c.get("/api/engram/diagnostics")
        data = resp.json()
        assert data["total_memories"] >= 1


# ── Phase 13: Lexon ─────────────────────────────────────


class TestLexonAPI:
    def test_parse_known(self, client: TestClient):
        resp = client.get("/api/lexon/parse?q=deploy")
        assert resp.status_code == 200
        data = resp.json()
        assert "resolved_tool" in data
        assert data["confidence"] > 0

    def test_parse_unknown(self, client: TestClient):
        resp = client.get(
            "/api/lexon/parse?q=xyzzy_unknown_phrase",
        )
        data = resp.json()
        assert data["resolved_tool"] == ""

    def test_learn(self, client: TestClient):
        resp = client.post(
            "/api/lexon/learn",
            json={"phrase": "ship it", "tool": "deploy"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "learned"

        resp = client.get("/api/lexon/parse?q=ship+it")
        data = resp.json()
        assert data["resolved_tool"] == "deploy"


# ── Phase 11: Mesh ──────────────────────────────────────


class TestMeshAPI:
    def test_mesh_status_enabled(self, client: TestClient):
        resp = client.get("/api/mesh/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert data["peers"] == 0
        assert "networks" in data

    def test_mesh_peers_empty(self, client: TestClient):
        resp = client.get("/api/mesh/peers")
        assert resp.status_code == 200
        assert resp.json()["peers"] == []

    def test_mesh_networks(self, client: TestClient):
        resp = client.get("/api/mesh/networks")
        assert resp.status_code == 200
        nets = resp.json()["networks"]
        assert len(nets) == 1
        assert nets[0]["org"] == "test-org"

    def test_mesh_quarantine_requires_org(
        self, client: TestClient,
    ):
        resp = client.get("/api/mesh/quarantine")
        assert resp.status_code == 422
        assert "error" in resp.json()

    def test_mesh_quarantine_with_org(
        self, client: TestClient,
    ):
        resp = client.get("/api/mesh/quarantine?org=test-org")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_mesh_add_peer(self, client: TestClient):
        resp = client.post(
            "/api/mesh/peers",
            json={
                "org": "test-org",
                "peer_id": "p1",
                "name": "remote",
                "address": "ws://x",
            },
        )
        assert resp.json()["status"] == "added"
        resp = client.get("/api/mesh/peers?org=test-org")
        assert len(resp.json()["peers"]) == 1


# ── Unconfigured state ──────────────────────────────────


class TestUnconfiguredState:
    """Verify graceful behavior when services are None."""

    @pytest.fixture
    def unconfigured_client(self) -> TestClient:
        app = FastAPI()
        app.state.cfg = MaggyConfig()
        app.state.configured = False
        app.state.budget = None
        app.state.routing = None
        app.state.events = None
        app.state.cikg = None
        app.state.planning = None
        app.state.deploy = None
        app.state.forge = None
        app.state.engram = None
        app.state.lexon = None
        app.state.mesh = None

        from maggy.api.routes_budget import router as r1
        from maggy.api.routes_cikg import router as r2
        from maggy.api.routes_deploy import router as r3
        from maggy.api.routes_engram import router as r4
        from maggy.api.routes_events import router as r5
        from maggy.api.routes_forge import router as r6
        from maggy.api.routes_lexon import router as r7
        from maggy.api.routes_mesh import router as r8
        from maggy.api.routes_planning import router as r9
        from maggy.api.routes_routing import router as r0

        for r in (r1, r2, r3, r4, r5, r6, r7, r8, r9, r0):
            app.include_router(r)
        return TestClient(app)

    def test_budget_unconfigured(
        self, unconfigured_client: TestClient,
    ):
        resp = unconfigured_client.get("/api/budget")
        assert resp.status_code == 200
        assert resp.json()["status"] == "unconfigured"

    def test_routing_unconfigured(
        self, unconfigured_client: TestClient,
    ):
        resp = unconfigured_client.get("/api/routing/heatmap")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_events_unconfigured(
        self, unconfigured_client: TestClient,
    ):
        resp = unconfigured_client.get("/api/events")
        assert resp.json() == []

    def test_mesh_unconfigured(
        self, unconfigured_client: TestClient,
    ):
        resp = unconfigured_client.get("/api/mesh/status")
        data = resp.json()
        assert data["enabled"] is False

    def test_engram_unconfigured(
        self, unconfigured_client: TestClient,
    ):
        resp = unconfigured_client.get("/api/engram/query")
        assert "error" in resp.json()

    def test_lexon_unconfigured(
        self, unconfigured_client: TestClient,
    ):
        resp = unconfigured_client.get("/api/lexon/parse?q=hi")
        assert "error" in resp.json()

    def test_deploy_unconfigured(
        self, unconfigured_client: TestClient,
    ):
        resp = unconfigured_client.get("/api/deploy/sessions")
        assert "error" in resp.json()

    def test_forge_unconfigured(
        self, unconfigured_client: TestClient,
    ):
        resp = unconfigured_client.get("/api/forge/status")
        assert "error" in resp.json()

    def test_planning_unconfigured(
        self, unconfigured_client: TestClient,
    ):
        resp = unconfigured_client.post(
            "/api/planning/generate",
            json={"task": "test"},
        )
        assert "error" in resp.json()

    def test_cikg_unconfigured(
        self, unconfigured_client: TestClient,
    ):
        resp = unconfigured_client.get("/api/cikg/landscape")
        assert "error" in resp.json()


# --- History Endpoint Tests ---


class TestHistoryEndpoints:
    """Tests for /api/history/* endpoints."""

    def test_providers(self, client: TestClient):
        resp = client.get("/api/history/providers")
        assert resp.status_code == 200
        assert "providers" in resp.json()

    def test_analyze(self, client: TestClient):
        resp = client.post("/api/history/analyze")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_sessions" in data
        assert "total_prompts" in data

    def test_report_empty(self, client: TestClient):
        resp = client.get("/api/history/report")
        assert resp.status_code == 200

    def test_sessions(self, client: TestClient):
        # First analyze to populate
        client.post("/api/history/analyze")
        resp = client.get("/api/history/sessions")
        assert resp.status_code == 200
        assert "sessions" in resp.json()

    def test_sessions_filter(self, client: TestClient):
        resp = client.get(
            "/api/history/sessions?provider=claude",
        )
        assert resp.status_code == 200


# --- Discovery + Enhanced Health ---


class TestDiscoveryEndpoint:
    def test_discovery_returns_data(
        self, client: TestClient,
    ):
        resp = client.get("/api/discovery")
        assert resp.status_code == 200
        data = resp.json()
        assert "clis" in data
        assert "repos" in data
        assert "tokens" in data

    def test_health_has_mode(
        self, client: TestClient,
    ):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "mode" in data
        assert data["mode"] in ("full", "local")


# --- Heartbeat Endpoint Tests ---


class TestHeartbeatEndpoints:
    def test_status_no_scheduler(self, client: TestClient):
        resp = client.get("/api/heartbeat/status")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_trigger_no_scheduler(self, client: TestClient):
        resp = client.post("/api/heartbeat/trigger/nope")
        assert resp.status_code == 503

    def test_status_with_scheduler(
        self, app_with_services: FastAPI,
    ):
        from maggy.heartbeat.scheduler import HeartbeatScheduler
        from unittest.mock import AsyncMock
        sched = HeartbeatScheduler()
        sched.register("test_job", AsyncMock(), 60)
        app_with_services.state.heartbeat = sched
        c = TestClient(app_with_services)
        resp = c.get("/api/heartbeat/status")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "test_job"


# --- Self-Improvement Endpoint Tests ---


class TestImproveEndpoints:
    def test_report_empty(self, client: TestClient):
        resp = client.get("/api/improve/report")
        assert resp.status_code == 200
        assert resp.json()["report"] is None

    def test_analyze_returns_report(
        self, client: TestClient,
    ):
        resp = client.post("/api/improve/analyze")
        assert resp.status_code == 200
        data = resp.json()
        assert "report" in data
        report = data["report"]
        assert "generated_at" in report
        assert "recommendations" in report

    def test_report_after_analyze(
        self, client: TestClient,
    ):
        client.post("/api/improve/analyze")
        resp = client.get("/api/improve/report")
        data = resp.json()
        assert data["report"] is not None
