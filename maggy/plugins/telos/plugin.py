"""Telos plugin — intent-grounded testing for Maggy."""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/telos", tags=["telos"])
_here = Path(__file__).resolve().parent


def _ensure(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, _here / filename,
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_scorer = _ensure("telos_ifs_scorer", "ifs_scorer.py")


def register(bus, manifest):
    logger.info("telos: registered")


async def on_project_connected(payload: dict) -> None:
    working_dir = payload.get("working_dir", "")
    project_key = payload.get("project_key", "")
    if not working_dir or not Path(working_dir).is_dir():
        return
    try:
        result = _scorer.score_project(working_dir)
        c = result.ifs.composite
        if c < 0.8:
            logger.warning(
                "telos: %s IFS=%.2f (low)", project_key, c,
            )
        else:
            logger.info(
                "telos: %s IFS=%.2f", project_key, c,
            )
    except Exception as e:
        logger.debug("telos: score failed: %s", e)


async def heartbeat_ifs() -> dict:
    return {"status": "ok", "plugin": "telos"}


@router.get("/status")
async def telos_status(
    project_dir: str = Query(...),
):
    result = _scorer.score_project(project_dir)
    return result.to_dict()
