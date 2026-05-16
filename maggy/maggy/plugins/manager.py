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
    """Discovers, loads, and manages plugins."""

    def __init__(self, bus: HookBus | None = None):
        self._bus = bus or HookBus()
        self._plugins: dict[str, PluginManifest] = {}
        self._modules: dict[str, Any] = {}

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
            spec = importlib.util.spec_from_file_location(
                f"maggy_plugin_{manifest.id}", entry,
            )
            if not spec or not spec.loader:
                return False
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            # Register hooks
            if hasattr(module, "register"):
                module.register(self._bus, manifest)

            self._plugins[manifest.id] = manifest
            self._modules[manifest.id] = module
            logger.info("Loaded plugin: %s v%d", manifest.id, manifest.version)
            return True
        except Exception as e:
            logger.warning("Failed to load plugin %s: %s", manifest.id, e)
            return False

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
