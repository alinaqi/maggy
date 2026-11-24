"""Guard: dead deploy/planning stubs and their API routes stay deleted."""

from __future__ import annotations

import importlib.util

import pytest

DEAD_MODULES = (
    "maggy.deploy",
    "maggy.planning",
    "maggy.models.plan",
    "maggy.api.routes_deploy",
    "maggy.api.routes_planning",
)
DEAD_PREFIXES = ("/api/deploy", "/api/planning")


@pytest.mark.parametrize("name", DEAD_MODULES)
def test_dead_module_is_gone(name: str) -> None:
    assert importlib.util.find_spec(name) is None, f"{name} should be deleted"


def _registered_paths() -> list[str]:
    from maggy.main import _ROUTERS
    return [route.path for r in _ROUTERS for route in r.routes]


@pytest.mark.parametrize("prefix", DEAD_PREFIXES)
def test_dead_routes_not_registered(prefix: str) -> None:
    hits = [p for p in _registered_paths() if p.startswith(prefix)]
    assert hits == [], f"routes still registered: {hits}"


def test_dead_services_not_on_app_state() -> None:
    from maggy.main import _TIER1_ATTRS
    assert "deploy" not in _TIER1_ATTRS
    assert "planning" not in _TIER1_ATTRS
