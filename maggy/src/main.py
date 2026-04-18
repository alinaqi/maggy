"""Maggy FastAPI app entrypoint.

Run with: python -m src.main
Or: uvicorn src.main:app --host 127.0.0.1 --port 8080
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src import config as config_mod
from src import providers
from src.api.routes import router as api_router
from src.services.competitor import CompetitorService
from src.services.executor import ExecutorService
from src.services.inbox import InboxService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("maggy")


def create_app() -> FastAPI:
    cfg = config_mod.load()

    app = FastAPI(title="Maggy", version="0.1.0")
    app.state.cfg = cfg
    app.state.configured = config_mod.is_configured()

    if app.state.configured:
        app.state.provider = providers.build(cfg)
        app.state.inbox = InboxService(cfg, app.state.provider)
        app.state.competitors = CompetitorService(cfg)
        app.state.executor = ExecutorService(cfg, app.state.provider)
        logger.info("Maggy ready — provider=%s, codebases=%d, domain=%s",
                    cfg.issue_tracker.provider, len(cfg.codebases), cfg.org.domain or "unset")
    else:
        logger.warning("Maggy is not configured — edit ~/.maggy/config.yaml and restart.")
        logger.warning("Copy claude-bootstrap/maggy/config.example.yaml to ~/.maggy/config.yaml")
        # Stay up so /api/health + /api/config can drive an onboarding UI,
        # but the runtime services are None — routes gate on app.state.configured
        # and return 503 instead of dereferencing.
        app.state.provider = None
        app.state.inbox = None
        app.state.competitors = None
        app.state.executor = None

    app.include_router(api_router)

    # Static files
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/")
        async def index():
            return FileResponse(str(static_dir / "index.html"))

    return app


app = create_app()


def main() -> None:
    """Console script entrypoint — runs uvicorn with the configured host/port.

    Referenced by `[project.scripts] maggy = "src.main:main"` in pyproject.toml.
    Can also be invoked with `python -m src.main`.
    """
    import uvicorn
    cfg = config_mod.load()
    uvicorn.run(
        "src.main:app",
        host=cfg.dashboard.host,
        port=cfg.dashboard.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
