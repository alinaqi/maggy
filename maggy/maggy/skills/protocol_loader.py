"""Load protocol YAML files from a directory."""
from __future__ import annotations

import logging
from pathlib import Path

from maggy.skills.protocol_models import Protocol, ProtocolStep

logger = logging.getLogger(__name__)


def load_protocols(directory: Path | str) -> list[Protocol]:
    d = Path(directory)
    if not d.is_dir():
        return []
    protos: list[Protocol] = []
    for f in sorted(d.glob("*.yaml")):
        proto = _parse_file(f)
        if proto:
            protos.append(proto)
    return protos


def _parse_file(path: Path) -> Protocol | None:
    try:
        import yaml
        data = yaml.safe_load(path.read_text())
    except Exception:
        logger.debug("Failed to parse %s", path)
        return None
    if not isinstance(data, dict) or "name" not in data:
        return None
    steps = [_parse_step(s) for s in data.get("steps", [])]
    return Protocol(
        name=data["name"],
        description=data.get("description", ""),
        triggers=data.get("triggers", []),
        steps=[s for s in steps if s],
    )


def _parse_step(raw: dict) -> ProtocolStep | None:
    if not isinstance(raw, dict) or "name" not in raw:
        return None
    return ProtocolStep(
        name=raw["name"],
        label=raw.get("label", raw["name"]),
        cmd=raw.get("cmd", ""),
        optional=bool(raw.get("optional", False)),
        condition=str(raw.get("condition", "")),
        requires=str(raw.get("requires", "")),
    )
