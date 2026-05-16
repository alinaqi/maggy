"""Maggy FastAPI app entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response

from maggy import config as config_mod
from maggy import providers
from maggy.api.routes import router as api_router
from maggy.api.routes_aggregator import router as aggregator_router
from maggy.api.routes_budget import router as budget_router
from maggy.api.routes_plugins import router as plugins_router
from maggy.api.routes_testing import router as testing_router
from maggy.api.routes_cikg import router as cikg_router
from maggy.api.routes_deploy import router as deploy_router
from maggy.api.routes_engram import router as engram_router
from maggy.api.routes_events import router as events_router
from maggy.api.routes_forge import router as forge_router
from maggy.api.routes_heartbeat import router as heartbeat_router
from maggy.api.routes_history import router as history_router
from maggy.api.routes_icpg import router as icpg_router
from maggy.api.routes_improve import router as improve_router
from maggy.api.routes_lexon import router as lexon_router
from maggy.api.routes_mesh import router as mesh_router
from maggy.api.routes_mesh_admin import router as mesh_admin_router
from maggy.api.routes_planning import router as planning_router
from maggy.api.routes_process import router as process_router
from maggy.api.routes_routing import router as routing_router
from maggy.api.routes_blueprints import router as blueprints_router
from maggy.api.routes_chat import router as chat_router
from maggy.api.routes_chat_sessions import router as chat_sessions_router
from maggy.api.routes_escalation import router as escalation_router
from maggy.api.routes_observability import router as observability_router
from maggy.api.routes_projects import router as projects_router
from maggy.api.routes_setup import router as setup_router
from maggy.api.routes_users import router as users_router
from maggy.api.routes_orchestrator import router as orchestrator_router
from maggy.mesh.ws_server import router as ws_mesh_router
from maggy.budget import BudgetManager
from maggy.event_spine.emitter import EventEmitter
from maggy.event_spine.store import EventStore
from maggy.history.service import HistoryService
from maggy.process.service import ProcessService
from maggy.routing import RoutingService
from maggy.services.competitor import CompetitorService
from maggy.services.executor import ExecutorService
from maggy.services.inbox import InboxService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("maggy")

_TIER1_ATTRS = ("budget", "routing", "events", "cikg", "planning", "deploy", "forge", "engram", "lexon", "mesh", "activity", "registry", "escalator", "observability")
_TIER2_ATTRS = ("provider", "inbox", "competitors", "executor", "process")


def _init_tier1(app: FastAPI, cfg) -> None:
    """Tier 1: local-only services."""
    db_dir = Path(cfg.storage.path).expanduser().parent
    app.state.budget = BudgetManager(cfg)
    app.state.routing = RoutingService(cfg)
    from maggy.blueprint_store import BlueprintStore
    app.state.blueprints = BlueprintStore(db_dir / "blueprints.db")
    app.state.events = EventEmitter(EventStore(db_dir / "events.db"))
    from maggy.cikg.graph import KnowledgeGraphService
    app.state.cikg = KnowledgeGraphService(db_dir / "cikg.db")
    from maggy.planning import PlanningService
    app.state.planning = PlanningService(cfg)
    from maggy.deploy import DeployService
    app.state.deploy = DeployService()
    from maggy.forge.connector import ForgeConnector
    app.state.forge = ForgeConnector()
    from maggy.engram.store import EngramStore
    app.state.engram = EngramStore(db_dir / "engram.db")
    from maggy.engram.seed import seed_if_empty
    seed_if_empty(app.state.engram)
    from maggy.lexon.router import LexonRouter
    app.state.lexon = LexonRouter()
    _init_mesh(app, cfg)
    from maggy.services.activity import ActivityService
    app.state.activity = ActivityService()
    app.state.history = HistoryService(db_path=db_dir / "history.db")
    from maggy.improve.service import Introspector
    app.state.introspector = Introspector(app.state)
    from maggy.services.chat import ChatManager
    from maggy.services.session_store import SessionStore
    session_store = SessionStore(db_dir / "sessions.db")
    app.state.chat = ChatManager(cfg, store=session_store)
    from maggy.registry import ProjectRegistry
    app.state.registry = ProjectRegistry(cfg)
    from maggy.escalation.protocol import Escalator
    app.state.escalator = Escalator(db_dir / "escalations.db")
    from maggy.observability.collector import ObservabilityCollector
    app.state.observability = ObservabilityCollector(db_dir / "observability.db")
    if cfg.orchestrator.enabled:
        from maggy.services.orchestrator import OrchestratorService
        app.state.orchestrator = OrchestratorService(cfg)
    else:
        app.state.orchestrator = None


def _init_mesh(app: FastAPI, cfg) -> None:
    """Wire MeshManager if enabled in config."""
    if not cfg.mesh.enabled or not cfg.mesh.org_key_secret:
        if cfg.mesh.enabled and not cfg.mesh.org_key_secret:
            logger.warning("Mesh disabled: MAGGY_MESH_SECRET not set")
        app.state.mesh = None
        return
    from maggy.mesh.manager import MeshManager
    from maggy.mesh.org_scanner import effective_orgs
    from maggy.mesh.store import MeshStore
    db_dir = Path(cfg.storage.path).expanduser().parent
    store = MeshStore(db_dir / "mesh.db")
    mgr = MeshManager(cfg.mesh, store)
    for org in effective_orgs(cfg.mesh.orgs, [], cfg.mesh.exclude_orgs):
        mgr.add_network(org)
    app.state.mesh = mgr


def _set_mode(app: FastAPI, cfg) -> None:
    """Initialize or skip Tier 2 based on credentials."""
    if config_mod._has_provider_credentials(cfg):
        app.state.provider = providers.build(cfg)
        app.state.inbox = InboxService(cfg, app.state.provider)
        app.state.competitors = CompetitorService(cfg)
        app.state.executor = ExecutorService(cfg, app.state.provider)
        app.state.process = ProcessService(cfg)
        app.state.mode = "full"
    else:
        for attr in _TIER2_ATTRS:
            setattr(app.state, attr, None)
        app.state.mode = "local"


async def _start_heartbeat(app: FastAPI) -> None:
    """Register and start the heartbeat scheduler."""
    cfg = app.state.cfg
    if not cfg.heartbeat.enabled or not app.state.configured:
        app.state.heartbeat = None
        return
    from maggy.heartbeat.scheduler import HeartbeatScheduler
    from maggy.heartbeat.jobs import refresh_history, expire_engrams, self_improve, mesh_heartbeat, collect_signals
    from functools import partial
    sched = HeartbeatScheduler()
    sched.register("refresh_history", partial(refresh_history, app), cfg.heartbeat.history_interval)
    sched.register("expire_engrams", partial(expire_engrams, app), cfg.heartbeat.engram_interval)
    sched.register("self_improve", partial(self_improve, app), cfg.heartbeat.improve_interval)
    sched.register("collect_signals", partial(collect_signals, app), cfg.heartbeat.improve_interval)
    if cfg.mesh.enabled:
        sched.register("mesh_heartbeat", partial(mesh_heartbeat, app), cfg.heartbeat.mesh_interval)
    await sched.start()
    app.state.heartbeat = sched
    logger.info("Heartbeat started — %d jobs", len(sched._jobs))
    # Load plugins
    from maggy.plugins.manager import get_plugin_manager
    pm = get_plugin_manager()
    loaded = pm.load_all()
    app.state.plugins = pm
    logger.info("Plugins loaded — %d active", loaded)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    await _start_heartbeat(app)
    await _bootstrap(app)
    yield
    if app.state.heartbeat:
        await app.state.heartbeat.stop()


async def _bootstrap(app: FastAPI) -> None:
    """Seed services with data on first startup."""
    history = getattr(app.state, "history", None)
    if history:
        try:
            history.analyze()
        except Exception as e:
            logger.warning("Bootstrap history failed: %s", e)

    introspector = getattr(app.state, "introspector", None)
    if introspector:
        try:
            introspector.analyze()
        except Exception as e:
            logger.warning("Bootstrap improve failed: %s", e)

    cikg = getattr(app.state, "cikg", None)
    cfg = getattr(app.state, "cfg", None)
    if cikg and cfg:
        try:
            _seed_cikg(cikg, cfg)
        except Exception as e:
            logger.warning("Bootstrap CIKG failed: %s", e)


def _seed_cikg(cikg, cfg) -> None:
    """Build initial knowledge graph from configured codebases."""
    from datetime import datetime, timezone

    from maggy.cikg.models import Node

    now = datetime.now(timezone.utc).isoformat()
    for cb in cfg.codebases:
        path = Path(cb.path).expanduser()
        if not path.exists():
            continue
        cikg.add_node(Node(
            id=f"codebase:{cb.key}", node_type="codebase",
            name=cb.key, description=str(path),
            metadata={"path": str(path)}, created_at=now,
        ))
        _add_language_nodes(cikg, cb.key, path, now)


def _add_language_nodes(cikg, codebase_key, path, now) -> None:
    """Detect languages in a codebase and add nodes + edges."""
    from maggy.cikg.models import Edge, Node

    ext_map = {
        ".py": "python", ".ts": "typescript",
        ".tsx": "typescript", ".js": "javascript",
        ".jsx": "javascript", ".go": "go",
        ".rs": "rust", ".java": "java",
        ".rb": "ruby", ".swift": "swift",
        ".kt": "kotlin", ".cs": "csharp",
    }
    skip_dirs = {
        "node_modules", ".git", "__pycache__", ".venv",
        "venv", "dist", "build", ".next", "target",
    }
    found: set[str] = set()
    # Only scan 2 levels deep to avoid slow recursive scan
    for child in path.iterdir():
        if child.name in skip_dirs:
            continue
        if child.is_file() and child.suffix in ext_map:
            found.add(ext_map[child.suffix])
        elif child.is_dir():
            try:
                for f in child.iterdir():
                    if f.is_file() and f.suffix in ext_map:
                        found.add(ext_map[f.suffix])
            except PermissionError:
                pass
        if len(found) >= 10:
            break
    for lang in found:
        node_id = f"lang:{lang}"
        cikg.add_node(Node(
            id=node_id, node_type="technology",
            name=lang, description=f"{lang} programming language",
            metadata={}, created_at=now,
        ))
        cikg.add_edge(Edge(
            source_id=f"codebase:{codebase_key}",
            target_id=node_id,
            edge_type="uses_technology",
        ))


class _NoCacheStatic(BaseHTTPMiddleware):
    """Add no-cache headers to /static responses."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/static"):
            response.headers["Cache-Control"] = "no-store"
        return response


_ROUTERS = (
    aggregator_router, api_router, blueprints_router, budget_router,
    chat_router, chat_sessions_router,
    cikg_router, deploy_router, engram_router, escalation_router, icpg_router,
    events_router, forge_router, heartbeat_router,
    history_router, improve_router, lexon_router,
    mesh_router, mesh_admin_router, observability_router,
    orchestrator_router, planning_router, plugins_router,
    process_router, projects_router, routing_router,
    setup_router, testing_router, users_router,
    ws_mesh_router,
)


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    cfg = config_mod.load()
    if cfg.dashboard.auth_mode == "local" and cfg.dashboard.host not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError(
            f"dashboard.auth_mode=\"local\" is only safe on loopback. "
            f"You configured host={cfg.dashboard.host!r} — set auth_mode=\"token\" and MAGGY_API_KEY, "
            f"or bind to 127.0.0.1."
        )
    app = FastAPI(title="Maggy", version="0.1.0", lifespan=lifespan)
    app.add_middleware(_NoCacheStatic)
    app.state.cfg = cfg
    app.state.configured = config_mod.is_configured()
    if app.state.configured:
        _init_tier1(app, cfg)
    else:
        for attr in _TIER1_ATTRS:
            setattr(app.state, attr, None)
        from maggy.services.activity import ActivityService
        app.state.activity = ActivityService()
        app.state.history = HistoryService()
        app.state.introspector = None
        from maggy.services.chat import ChatManager
        from maggy.services.session_store import SessionStore
        db_dir = Path(cfg.storage.path).expanduser().parent
        session_store = SessionStore(db_dir / "sessions.db")
        app.state.chat = ChatManager(cfg, store=session_store)
    _set_mode(app, cfg)
    logger.info("Maggy ready (%s) — codebases=%d", app.state.mode, len(cfg.codebases))
    for r in _ROUTERS:
        app.include_router(r)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        @app.get("/")
        async def index():
            return FileResponse(
                str(static_dir / "index.html"),
                headers={"Cache-Control": "no-store"},
            )
    return app


def reconfigure(app: FastAPI) -> None:
    """Reload config and reinitialize services."""
    cfg = config_mod.load(refresh=True)
    app.state.cfg = cfg
    app.state.configured = config_mod.is_configured()
    if app.state.configured:
        _init_tier1(app, cfg)
    _set_mode(app, cfg)
    logger.info("Reconfigured — mode=%s", app.state.mode)


app = create_app()


def _print_banner(host: str, port: int) -> None:
    """Print startup banner with usage instructions."""
    url = f"http://{host}:{port}"
    print("\n\033[1;38;5;208m  Maggy\033[0m")
    print(f"  Dashboard: \033[4m{url}\033[0m")
    print()
    print(
        "  \033[33mKeep this terminal open\033[0m"
        " — Maggy runs here."
    )
    print(
        "  Use other terminals for Claude Code"
        " sessions."
    )
    print(
        "  Maggy Chat auto-connects to all"
        " active sessions."
    )
    print(
        "\n  Press Ctrl+C to stop.\n"
    )


def main() -> None:
    """Console script entrypoint."""
    import uvicorn
    cfg = config_mod.load()
    _print_banner(cfg.dashboard.host, cfg.dashboard.port)
    uvicorn.run(
        "maggy.main:app",
        host=cfg.dashboard.host,
        port=cfg.dashboard.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
