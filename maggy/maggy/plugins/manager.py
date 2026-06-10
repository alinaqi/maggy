"""Plugin Manager — discover, validate, execute plugins via typed event bus.

mWP design: opinionated, not flexible-theater. Plugins subscribe to
typed domain events. Core knows nothing about specific integrations.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

logger = logging.getLogger(__name__)

PLUGIN_DIRS = [
    Path.home() / ".maggy" / "plugins",          # User-installed
    Path(__file__).parent / "plugins",           # Built-in (maggy/maggy/plugins/)
    Path(__file__).parent.parent.parent / "plugins",  # Repo root (plugins/)
]

MANIFEST_FILE = "plugin.yaml"


@dataclass
class PluginManifest:
    id: str
    version: int
    entrypoint: str
    permissions: list[str] = field(default_factory=list)
    hooks: list[dict] = field(default_factory=list)
    config: dict = field(default_factory=dict)
    path: str = ""
    router: str = ""           # "module:router_name" for FastAPI router
    heartbeat: list[dict] = field(default_factory=list)  # [{name, interval_seconds, fn}]

    @classmethod
    def from_yaml(cls, path: Path) -> PluginManifest | None:
        try:
            data = yaml.safe_load(path.read_text())
            return cls(
                id=data["id"], version=data["version"],
                entrypoint=data["entrypoint"],
                permissions=data.get("permissions", []),
                hooks=data.get("hooks", []),
                config=data.get("config", {}),
                path=str(path.parent),
                router=data.get("router", ""),
                heartbeat=data.get("heartbeat", []),
            )
        except Exception as e:
            logger.warning("Invalid plugin manifest %s: %s", path, e)
            return None


@dataclass
class HookEvent:
    name: str
    payload: dict = field(default_factory=dict)


class HookBus:
    """Typed event bus — plugins subscribe, core emits."""

    def __init__(self):
        self._handlers: dict[str, list[tuple[str, Callable]]] = {}

    def subscribe(self, event: str, plugin_id: str, handler: Callable):
        self._handlers.setdefault(event, []).append((plugin_id, handler))

    async def emit(self, event: HookEvent):
        handlers = self._handlers.get(event.name, [])
        if not handlers:
            return
        for plugin_id, handler in handlers:
            try:
                await handler(event.payload)
                logger.debug("Plugin %s handled %s", plugin_id, event.name)
            except Exception as e:
                logger.warning("Plugin %s failed %s: %s", plugin_id, event.name, e)


class PluginManager:
    """Discovers, loads, and manages plugins. Supports router + heartbeat registration."""

    def __init__(self, bus: HookBus | None = None, app=None, scheduler=None):
        self._bus = bus or HookBus()
        self._app = app          # FastAPI app for router registration
        self._scheduler = scheduler  # HeartbeatScheduler for job registration
        self._plugins: dict[str, PluginManifest] = {}
        self._modules: dict[str, Any] = {}
        self._routers: dict[str, Any] = {}   # loaded routers by plugin id
        self._jobs: dict[str, str] = {}      # job_name → plugin_id mapping

    @property
    def bus(self) -> HookBus:
        return self._bus

    @property
    def plugins(self) -> dict[str, PluginManifest]:
        return dict(self._plugins)

    def discover(self) -> list[PluginManifest]:
        manifests = []
        for base in PLUGIN_DIRS:
            if not base.exists():
                continue
            for manifest_path in base.rglob(MANIFEST_FILE):
                m = PluginManifest.from_yaml(manifest_path)
                if m:
                    manifests.append(m)
        return manifests

    def load_all(self) -> int:
        loaded = 0
        for manifest in self.discover():
            if self._load_plugin(manifest):
                loaded += 1
        logger.info("Plugin manager loaded %d plugins", loaded)
        return loaded

    def _load_plugin(self, manifest: PluginManifest) -> bool:
        if manifest.id in self._plugins:
            logger.debug("Plugin %s already loaded", manifest.id)
            return False

        try:
            entry = Path(manifest.path) / manifest.entrypoint
            mod_name = f"maggy_plugin_{manifest.id}"
            spec = importlib.util.spec_from_file_location(mod_name, entry)
            if not spec or not spec.loader:
                return False
            module = importlib.util.module_from_spec(spec)
            module.__package__ = mod_name  # Fix Python 3.14 dataclass importlib bug
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)

            # Register hooks
            if hasattr(module, "register"):
                module.register(self._bus, manifest)

            # Register FastAPI router
            if manifest.router and self._app:
                self._register_router(manifest, module)

            # Register heartbeat jobs
            if manifest.heartbeat and self._scheduler:
                self._register_heartbeat(manifest, module)

            # Wire manifest hook subscriptions
            self._wire_hooks(manifest, module)

            self._plugins[manifest.id] = manifest
            self._modules[manifest.id] = module
            logger.info("Loaded plugin: %s v%d (router=%s, heartbeat=%d jobs)",
                       manifest.id, manifest.version,
                       "yes" if manifest.router else "no",
                       len(manifest.heartbeat))
            return True
        except Exception as e:
            logger.warning("Failed to load plugin %s: %s", manifest.id, e)
            return False

    def _wire_hooks(self, manifest: PluginManifest, module) -> None:
        """Subscribe manifest-declared hooks to the event bus."""
        for hook in manifest.hooks:
            event = hook.get("event", "")
            fn_name = hook.get("fn", "")
            fn = getattr(module, fn_name, None) if fn_name else None
            if not fn or not event:
                continue
            self._bus.subscribe(event, manifest.id, fn)
            logger.info(
                "Plugin %s: subscribed %s -> %s",
                manifest.id, event, fn_name,
            )

    def _register_router(self, manifest: PluginManifest, module):
        """Load and register a FastAPI router from a plugin."""
        try:
            # Format: "module_name:router_var" or just "router"
            parts = manifest.router.split(":")
            router_name = parts[-1]
            router = getattr(module, router_name, None)
            if router and hasattr(router, "routes"):
                self._app.include_router(router)
                self._routers[manifest.id] = router
                logger.info("Plugin %s: registered router %s", manifest.id, router_name)
        except Exception as e:
            logger.warning("Plugin %s router failed: %s", manifest.id, e)

    def _register_heartbeat(self, manifest: PluginManifest, module):
        """Register plugin heartbeat jobs with the scheduler."""
        for job_spec in manifest.heartbeat:
            job_name = job_spec.get("name", f"{manifest.id}_job")
            interval = job_spec.get("interval_seconds", 300)
            fn_name = job_spec.get("fn", "")
            fn = getattr(module, fn_name, None) if fn_name else None

            if not fn:
                logger.warning("Plugin %s: heartbeat job %s has no function",
                             manifest.id, job_name)
                continue

            try:
                self._scheduler.register(job_name, fn, interval)
                self._jobs[job_name] = manifest.id
                logger.info("Plugin %s: registered heartbeat %s (every %ds)",
                          manifest.id, job_name, interval)
            except ValueError:
                logger.debug("Heartbeat job %s already registered", job_name)
            except Exception as e:
                logger.warning("Plugin %s heartbeat %s failed: %s",
                             manifest.id, job_name, e)

    async def emit(self, event_name: str, payload: dict | None = None):
        """Emit a typed event to all subscribed plugins."""
        await self._bus.emit(HookEvent(name=event_name, payload=payload or {}))


# Singleton
_plugin_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager
