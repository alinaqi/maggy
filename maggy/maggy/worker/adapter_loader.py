"""Load adapters: shipped YAML, each replaceable by ~/.maggy/adapters/<name>.yaml."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from maggy.harness.errors import HarnessConfigError, schema_problems
from maggy.harness.loader import _load_yaml
from maggy.worker.adapter_spec import AdapterSpec

SHIPPED_DIR = Path(__file__).parent / "adapters"


class AdapterConfigError(HarnessConfigError):
    """An adapter file is invalid; the message names the file and key."""


def default_user_dir() -> Path:
    return Path.home() / ".maggy" / "adapters"


def load_adapters(shipped_dir: Path | None = None,
                  user_dir: Path | None = None) -> dict[str, AdapterSpec]:
    """All adapters by name; a user file replaces the shipped one whole."""
    files = _adapter_files(shipped_dir or SHIPPED_DIR)
    files.update(_adapter_files(user_dir or default_user_dir()))
    return {name: _parse(path) for name, path in sorted(files.items())}


def load_adapter(name: str, shipped_dir: Path | None = None,
                 user_dir: Path | None = None) -> AdapterSpec:
    adapters = load_adapters(shipped_dir, user_dir)
    if name not in adapters:
        raise KeyError(f"no adapter named {name!r}")
    return adapters[name]


def _adapter_files(directory: Path) -> dict[str, Path]:
    if not directory.is_dir():
        return {}
    return {path.stem: path for path in directory.glob("*.yaml")}


def _parse(path: Path) -> AdapterSpec:
    try:
        raw = _load_yaml(path)
    except HarnessConfigError as exc:
        raise AdapterConfigError(path, exc.problems) from exc
    try:
        spec = AdapterSpec.model_validate(raw)
    except ValidationError as exc:
        raise AdapterConfigError(path, schema_problems(exc, raw)) from exc
    if spec.name != path.stem:
        raise AdapterConfigError(path, [f"name: {spec.name!r} must match file name {path.stem!r}"])
    return spec
